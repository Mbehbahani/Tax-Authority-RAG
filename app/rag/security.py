"""RBAC authorization filters and audit logging.

Every factor that determines access is computed from the UserContext and the
chunk's front-matter metadata. The LLM is never an authorization component.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Iterable

from .models import Chunk, UserContext

audit_logger = logging.getLogger("tax_rag.audit")


_ROLE_INHERITANCE: dict[str, tuple[str, ...]] = {
    "helpdesk": ("helpdesk",),
    "tax_inspector": ("tax_inspector", "helpdesk"),
    "legal_counsel": ("legal_counsel", "tax_inspector", "helpdesk"),
    "fiod_investigator": ("fiod_investigator", "tax_inspector", "helpdesk"),
}


@dataclass(frozen=True)
class AuthFilter:
    """Concrete filter values used to build both an OpenSearch query and the
    in-memory predicate. Keeping both paths driven by the same dataclass avoids
    drift between the fake backend and the real backend.
    """

    role: str
    effective_roles: tuple[str, ...]
    clearance: int
    need_to_know_groups: tuple[str, ...]
    denied_classification_tags: tuple[str, ...]

    def to_opensearch_filter(self) -> dict[str, Any]:
        return {
            "bool": {
                "filter": [
                    {"terms": {"allowed_roles": list(self.effective_roles)}},
                    {"range": {"classification_level": {"lte": self.clearance}}},
                ],
                "must_not": [
                    {"term": {"classification_tags": tag}}
                    for tag in self.denied_classification_tags
                ],
            }
        }

    def scope_hash(self) -> str:
        """Stable hash of (role, clearance, need-to-know, denied tags) for
        cache-key isolation.
        """

        payload = {
            "role": self.role,
            "effective_roles": sorted(self.effective_roles),
            "clearance": self.clearance,
            "ntk": sorted(self.need_to_know_groups),
            "denied": sorted(self.denied_classification_tags),
        }
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:20]


# Classification tags that helpdesk / non-FIOD roles must never see.
_RESTRICTED_TAGS_FOR_NON_FIOD = ("FIOD", "fraud_investigation")


def build_auth_filter(user: UserContext) -> AuthFilter:
    denied: tuple[str, ...]
    if user.role == "fiod_investigator":
        denied = ()
    else:
        denied = _RESTRICTED_TAGS_FOR_NON_FIOD
    effective_roles = _ROLE_INHERITANCE.get(user.role, (user.role,))
    return AuthFilter(
        role=user.role,
        effective_roles=effective_roles,
        clearance=user.clearance,
        need_to_know_groups=tuple(user.need_to_know_groups),
        denied_classification_tags=denied,
    )


def is_authorized(chunk: Chunk, user: UserContext, *, auth: AuthFilter | None = None) -> bool:
    """Single source of truth for RBAC decisions.

    Rules (applied before scoring, reranking, prompt, and cache lookup):
      1. chunk.allowed_roles must intersect the user's effective roles.
      2. chunk.classification_level must be <= user.clearance.
      3. chunks with FIOD/fraud_investigation tags are denied for all non-FIOD
         roles, regardless of clearance.
      4. chunks with a case_scope must match the user's need_to_know_groups.
    """

    auth = auth or build_auth_filter(user)
    if not set(chunk.allowed_roles).intersection(auth.effective_roles):
        return False
    if chunk.classification_level > user.clearance:
        return False
    for tag in auth.denied_classification_tags:
        if tag in chunk.classification_tags:
            return False
    if chunk.case_scope and chunk.case_scope not in auth.need_to_know_groups:
        return False
    return True


def authorized_only(
    chunks: Iterable[Chunk], user: UserContext, *, auth: AuthFilter | None = None
) -> list[Chunk]:
    auth = auth or build_auth_filter(user)
    return [c for c in chunks if is_authorized(c, user, auth=auth)]


def audit(event: str, **fields: Any) -> None:
    """Emit a structured audit record.

    Local PoC writes to the standard logging subsystem. Production replaces
    the handler with a CloudWatch/OTel exporter without changing callers.
    """

    payload = {"event": event, **fields}
    audit_logger.info(json.dumps(payload, default=str))
