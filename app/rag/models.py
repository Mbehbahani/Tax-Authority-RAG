"""Shared data structures for the Tax Authority RAG local PoC.

Plain dataclasses keep the PoC dependency-light (no pydantic requirement on the
core) and preserve a stable shape when swapping the retrieval backend from the
in-memory fake to a real OpenSearch client.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UserContext:
    """Authorization context propagated through every pipeline state."""

    user_id: str
    role: str
    clearance: int
    department_scope: tuple[str, ...] = ()
    need_to_know_groups: tuple[str, ...] = ()

    @property
    def classification_scope(self) -> str:
        return f"cls_lte_{self.clearance}"

    @property
    def role_scope(self) -> str:
        return self.role


@dataclass
class Chunk:
    """A single legally-structured chunk.

    The field set mirrors the expected OpenSearch mapping in
    tests/integration/opensearch_index_config_expected.json so that swapping
    the retrieval backend requires no schema change.
    """

    chunk_id: str
    document_id: str
    document_name: str
    source_type: str
    text: str
    article: str
    paragraph: str
    section_path: list[str] = field(default_factory=list)
    effective_from: str | None = None
    effective_to: str | None = None
    version: str | None = None
    classification_level: int = 1
    allowed_roles: list[str] = field(default_factory=list)
    classification_tags: list[str] = field(default_factory=list)
    case_scope: str | None = None
    ecli: str | None = None
    embedding: list[float] = field(default_factory=list)

    def to_index_doc(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "source_type": self.source_type,
            "text": self.text,
            "article": self.article,
            "paragraph": self.paragraph,
            "section_path": list(self.section_path),
            "effective_from": self.effective_from,
            "effective_to": self.effective_to,
            "version": self.version,
            "classification_level": self.classification_level,
            "allowed_roles": list(self.allowed_roles),
            "classification_tags": list(self.classification_tags),
            "case_scope": self.case_scope,
            "ecli": self.ecli,
            "embedding": list(self.embedding),
        }


@dataclass
class Citation:
    """One citation for one atomic claim in the answer."""

    chunk_id: str
    document_id: str
    document_name: str
    article: str
    paragraph: str

    def is_complete(self) -> bool:
        return bool(
            self.chunk_id
            and self.document_id
            and self.document_name
            and self.article
            and self.paragraph
        )

    def format(self) -> str:
        return f"({self.document_name}, Article {self.article}, Paragraph {self.paragraph})"


@dataclass
class GraderResult:
    label: str  # Relevant | Ambiguous | Irrelevant
    confidence: float
    reasons: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    required_action: str = ""
