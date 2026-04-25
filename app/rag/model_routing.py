"""Stage 3 model-routing and evaluation helpers.

The router is deliberately conservative: deterministic mode remains the
default, Haiku-class models can be used only for low-risk/simple tasks, and
Sonnet-class models are selected for legal interpretation, fraud, ambiguity,
or any high-risk wording.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from typing import Callable

from .models import UserContext


LOW_RISK_MARKERS = ("what is", "define", "summarize", "helpdesk", "documentation")
HIGH_RISK_MARKERS = (
    "legal interpretation",
    "ruling",
    "ecli",
    "fraud",
    "fiod",
    "investigation",
    "tax year",
    "deduction limit",
    "percentage",
    "deductible",
    "exact",
    "court",
    "appeal",
)


@dataclass(frozen=True)
class RoutingDecision:
    mode: str
    model_id: str
    reason: str
    risk_level: str


@dataclass(frozen=True)
class EvaluationResult:
    mode: str
    query: str
    user_id: str
    abstained: bool
    citation_completeness: float
    citation_accuracy: float
    rbac_leakage_count: int
    latency_seconds: float
    passed: bool


class ModelRouter:
    def __init__(
        self,
        *,
        deterministic_model_id: str = "deterministic-extractive-v1",
        haiku_model_id: str | None = None,
        sonnet_model_id: str | None = None,
    ) -> None:
        self.deterministic_model_id = deterministic_model_id
        self.haiku_model_id = haiku_model_id or os.getenv(
            "BEDROCK_FAST_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"
        )
        self.sonnet_model_id = sonnet_model_id or os.getenv(
            "BEDROCK_GENERATION_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0"
        )

    def route(self, query: str, user: UserContext, *, mode: str | None = None) -> RoutingDecision:
        selected_mode = (mode or os.getenv("MODEL_ROUTING_MODE", "deterministic")).lower()
        risk = classify_query_risk(query, user)

        if selected_mode == "deterministic":
            return RoutingDecision(
                mode="deterministic",
                model_id=self.deterministic_model_id,
                reason="offline deterministic safety baseline",
                risk_level=risk,
            )

        if selected_mode == "haiku":
            if risk != "low":
                return RoutingDecision(
                    mode="sonnet",
                    model_id=self.sonnet_model_id,
                    reason="haiku requested but query is high-risk; escalated to Sonnet",
                    risk_level=risk,
                )
            return RoutingDecision(
                mode="haiku",
                model_id=self.haiku_model_id,
                reason="low-risk query eligible for fast model",
                risk_level=risk,
            )

        if selected_mode in {"sonnet", "high_risk"}:
            return RoutingDecision(
                mode="sonnet",
                model_id=self.sonnet_model_id,
                reason="explicit high-risk/sonnet route",
                risk_level=risk,
            )

        return RoutingDecision(
            mode="deterministic",
            model_id=self.deterministic_model_id,
            reason=f"unknown route {selected_mode}; using deterministic fallback",
            risk_level=risk,
        )


def classify_query_risk(query: str, user: UserContext) -> str:
    low = query.lower()
    if user.role in {"fiod_investigator", "legal_counsel"}:
        return "high"
    if any(marker in low for marker in HIGH_RISK_MARKERS):
        return "high"
    if re.search(r"\b\d+(\.\d+)?\s*(%|percent|eur|euro)\b", low):
        return "high"
    if any(marker in low for marker in LOW_RISK_MARKERS):
        return "low"
    return "medium"


def evaluate_service_mode(
    *,
    service_factory: Callable[[], object],
    user: UserContext,
    query: str,
    mode: str,
) -> EvaluationResult:
    start = time.perf_counter()
    service = service_factory()
    result = service.ask(user, query)  # type: ignore[attr-defined]
    elapsed = time.perf_counter() - start
    citations = result.citations
    complete = bool(citations) and all(
        c.get("chunk_id") and c.get("document_id") and c.get("document_name") and c.get("article") and c.get("paragraph")
        for c in citations
    )
    retrieved_ids = set(result.retrieved_chunk_ids)
    citation_ids = {c.get("chunk_id") for c in citations}
    citation_accuracy = 1.0 if citation_ids.issubset(retrieved_ids) else 0.0
    citation_completeness = 1.0 if complete or result.abstained else 0.0
    leakage_count = sum(1 for c in citations if c.get("document_id") == "DOC-FIOD-001" and user.role != "fiod_investigator")
    passed = citation_completeness == 1.0 and citation_accuracy == 1.0 and leakage_count == 0
    return EvaluationResult(
        mode=mode,
        query=query,
        user_id=user.user_id,
        abstained=result.abstained,
        citation_completeness=citation_completeness,
        citation_accuracy=citation_accuracy,
        rbac_leakage_count=leakage_count,
        latency_seconds=elapsed,
        passed=passed,
    )
