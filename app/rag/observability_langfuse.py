"""Optional Langfuse Cloud export for evaluation and observability results.

Exports sanitised evaluation data to Langfuse Cloud so results can be viewed
in the hosted dashboard.  The export is a parallel, non-blocking layer that
never changes deterministic evaluation logic.

Design constraints:
- Disabled by default (``ENABLE_LANGFUSE`` env var must be ``true``/``1``/
  ``yes`` to activate).
- Safe to import when ``langfuse`` is not installed; all entry points return
  gracefully without raising.
- No secrets, no raw legal document text, no PII are sent.  Payloads contain
  only IDs, hashes, counts, metric scores, and decision labels.
- A single ``LangfuseExporter`` instance should be created per run; call
  ``flush()`` at the end of each run to ensure all queued events are sent.

Environment variables (all optional when Langfuse is disabled):
    ENABLE_LANGFUSE      — "true" / "1" / "yes" to enable (default "false")
    LANGFUSE_PUBLIC_KEY  — Langfuse project public key
    LANGFUSE_SECRET_KEY  — Langfuse project secret key
    LANGFUSE_BASE_URL    — Langfuse host (default "https://cloud.langfuse.com")

What appears in the Langfuse UI per exported scenario:
    - A **Trace** named ``tax_rag.eval.<suite>.<scenario_id>`` with:
        - trace.user_id  = sanitised role label (never the actual user PK)
        - trace.metadata = { scenario_id, suite, mode, final_decision,
                             cache_hit, latency_seconds }
    - A **Score** per metric (one Score object per numeric metric):
        - citation_accuracy
        - rbac_leakage_count  (inverted: 1.0 when 0 leaks)
        - precision_at_k, recall_at_k, mrr_at_k, ndcg_at_k  (if present)
        - answer_relevancy, faithfulness  (if DeepEval scores present)
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------


def _langfuse_importable() -> bool:
    try:
        import langfuse  # noqa: F401
        return True
    except Exception:
        return False


def is_langfuse_enabled() -> bool:
    """Return True only when ENABLE_LANGFUSE=true/1/yes AND langfuse is installed."""
    flag = os.getenv("ENABLE_LANGFUSE", "false").strip().lower()
    return flag in ("1", "true", "yes") and _langfuse_importable()


# ---------------------------------------------------------------------------
# Sanitisation helpers
# ---------------------------------------------------------------------------


def _sanitise_role(user_id: str, role: str) -> str:
    """Return a role label safe to send externally.

    The actual user_id (which may be an internal employee identifier) is
    replaced with a stable hash prefix so traces are linkable within a run
    without exposing the raw identifier.
    """
    uid_hash = hashlib.sha256(user_id.encode()).hexdigest()[:8]
    return f"{role}_{uid_hash}"


def _decision_label(abstained: bool, error: bool = False) -> str:
    if error:
        return "error"
    return "abstain" if abstained else "answer"


# ---------------------------------------------------------------------------
# Exported scenario payload — the minimal sanitised record
# ---------------------------------------------------------------------------


@dataclass
class LangfuseScenarioPayload:
    """Sanitised, export-safe representation of a single evaluated scenario."""

    scenario_id: str
    suite: str
    mode: str
    sanitised_role: str          # role label + hashed user_id prefix
    final_decision: str          # "answer" | "abstain" | "error"
    cache_hit: bool
    latency_seconds: float
    citation_accuracy: float
    rbac_leakage_count: int
    # IR ranking (None when gold labels absent)
    precision_at_k: float | None = None
    recall_at_k: float | None = None
    mrr_at_k: float | None = None
    ndcg_at_k: float | None = None
    # DeepEval quality (None when DeepEval disabled)
    answer_relevancy: float | None = None
    faithfulness: float | None = None
    # Optional retrieval attempt count (if tracked)
    retrieval_attempt_count: int | None = None
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Builder: convert ScenarioEvaluation → LangfuseScenarioPayload
# ---------------------------------------------------------------------------


def build_payload(
    row: Any,                          # ScenarioEvaluation
    *,
    deepeval_row: Any | None = None,   # DeepEvalScenarioResult | None
    users: dict[str, Any] | None = None,
) -> LangfuseScenarioPayload:
    """Build a sanitised ``LangfuseScenarioPayload`` from evaluation objects.

    Parameters
    ----------
    row:
        A ``ScenarioEvaluation`` instance.
    deepeval_row:
        Optional ``DeepEvalScenarioResult`` for the same scenario.
    users:
        Optional ``{user_id: UserContext}`` mapping; used to read the role
        label without exposing the raw user_id.
    """
    role = "unknown"
    if users and row.user_id in users:
        user_ctx = users[row.user_id]
        role = getattr(user_ctx, "role", "unknown")

    # Determine final decision from the row fields available
    # (ScenarioEvaluation doesn't carry abstained directly — use
    # abstention_correctness + expected-behavior inference)
    abstained = row.abstention_correctness == 1.0 and not row.answer_relevance

    de_relevancy: float | None = None
    de_faithfulness: float | None = None
    if deepeval_row is not None:
        de_relevancy = getattr(deepeval_row, "answer_relevancy", None)
        de_faithfulness = getattr(deepeval_row, "faithfulness", None)

    return LangfuseScenarioPayload(
        scenario_id=row.scenario_id,
        suite=row.suite,
        mode=row.mode,
        sanitised_role=_sanitise_role(row.user_id, role),
        final_decision=_decision_label(abstained),
        cache_hit=bool(row.cache_hit),
        latency_seconds=float(row.latency_seconds),
        citation_accuracy=float(row.citation_accuracy),
        rbac_leakage_count=int(row.rbac_leakage_count),
        precision_at_k=getattr(row, "scenario_precision_at_k", None),
        recall_at_k=getattr(row, "scenario_recall_at_k", None),
        mrr_at_k=getattr(row, "scenario_mrr_at_k", None),
        ndcg_at_k=getattr(row, "scenario_ndcg_at_k", None),
        answer_relevancy=de_relevancy,
        faithfulness=de_faithfulness,
    )


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


class LangfuseExporter:
    """Lightweight wrapper around the Langfuse Python SDK.

    Usage::

        exporter = LangfuseExporter()          # disabled when env not set
        for row in scenario_rows:
            payload = build_payload(row, users=users)
            exporter.export_scenario(payload)
        exporter.flush()

    When ``is_langfuse_enabled()`` is ``False`` all methods are no-ops and
    no network calls are made.
    """

    def __init__(self) -> None:
        self._enabled = is_langfuse_enabled()
        self._client: Any = None
        if self._enabled:
            self._client = self._build_client()

    # -------------------------------------------------------------- private

    @staticmethod
    def _build_client() -> Any:
        """Build the Langfuse client from environment variables."""
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")
        base_url = os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            import warnings
            warnings.warn(
                "ENABLE_LANGFUSE=true but LANGFUSE_PUBLIC_KEY or "
                "LANGFUSE_SECRET_KEY is not set.  Langfuse export disabled.",
                stacklevel=3,
            )
            return None

        try:
            from langfuse import Langfuse
            return Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=base_url,
            )
        except Exception as exc:
            import warnings
            warnings.warn(
                f"Could not initialise Langfuse client: {exc}. "
                "Langfuse export disabled.",
                stacklevel=3,
            )
            return None

    # -------------------------------------------------------------- public

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    def export_scenario(self, payload: LangfuseScenarioPayload) -> None:
        """Export a single scenario as a Langfuse event + scores.

        No-op when disabled.
        """
        if not self.enabled:
            return

        trace_name = f"tax_rag.eval.{payload.suite}.{payload.scenario_id}"

        try:
            trace_id = self._client.create_trace_id(seed=trace_name)
            event = self._client.create_event(
                trace_context={"trace_id": trace_id},
                name=trace_name,
                input=None,
                output=None,
                metadata={
                    "scenario_id": payload.scenario_id,
                    "suite": payload.suite,
                    "mode": payload.mode,
                    "sanitised_role": payload.sanitised_role,
                    "final_decision": payload.final_decision,
                    "cache_hit": payload.cache_hit,
                    "latency_seconds": payload.latency_seconds,
                },
            )
            self._export_scores(trace_id, payload)
        except Exception as exc:
            import warnings
            warnings.warn(
                f"Langfuse export failed for {payload.scenario_id}: {exc}",
                stacklevel=2,
            )

    def _export_scores(self, trace_id: str, payload: LangfuseScenarioPayload) -> None:
        """Attach numeric scores to a Langfuse trace."""
        scores: list[tuple[str, float]] = [
            ("citation_accuracy", payload.citation_accuracy),
            # Invert rbac_leakage: 1.0 = no leakage (desired), 0.0 = leak detected.
            ("rbac_no_leakage", 1.0 if payload.rbac_leakage_count == 0 else 0.0),
        ]
        if payload.precision_at_k is not None:
            scores.append(("precision_at_k", payload.precision_at_k))
        if payload.recall_at_k is not None:
            scores.append(("recall_at_k", payload.recall_at_k))
        if payload.mrr_at_k is not None:
            scores.append(("mrr_at_k", payload.mrr_at_k))
        if payload.ndcg_at_k is not None:
            scores.append(("ndcg_at_k", payload.ndcg_at_k))
        if payload.answer_relevancy is not None:
            scores.append(("answer_relevancy", payload.answer_relevancy))
        if payload.faithfulness is not None:
            scores.append(("faithfulness", payload.faithfulness))

        for name, value in scores:
            try:
                self._client.create_score(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                )
            except Exception:
                pass   # individual score failures must not abort the export

    def flush(self) -> None:
        """Flush pending events to Langfuse.  No-op when disabled."""
        if not self.enabled:
            return
        try:
            self._client.flush()
        except Exception as exc:
            import warnings
            warnings.warn(f"Langfuse flush failed: {exc}", stacklevel=2)


# ---------------------------------------------------------------------------
# Convenience: export a full evaluation run
# ---------------------------------------------------------------------------


def export_evaluation_run(
    rows: list[Any],
    *,
    users: dict[str, Any] | None = None,
    deepeval_rows: list[Any] | None = None,
    exporter: LangfuseExporter | None = None,
) -> LangfuseExporter:
    """Export all ``ScenarioEvaluation`` rows and return the exporter.

    Parameters
    ----------
    rows:
        List of ``ScenarioEvaluation`` instances from the evaluation run.
    users:
        Optional ``{user_id: UserContext}`` mapping for role resolution.
    deepeval_rows:
        Optional list of ``DeepEvalScenarioResult`` instances.  Matched to
        rows by ``scenario_id``.
    exporter:
        Optional pre-built ``LangfuseExporter``.  A new one is created when
        ``None``.
    """
    if exporter is None:
        exporter = LangfuseExporter()

    # Build a lookup map for DeepEval rows by scenario_id.
    de_map: dict[str, Any] = {}
    if deepeval_rows:
        for de_row in deepeval_rows:
            de_map[de_row.scenario_id] = de_row

    for row in rows:
        de_row = de_map.get(row.scenario_id)
        payload = build_payload(row, deepeval_row=de_row, users=users)
        exporter.export_scenario(payload)

    exporter.flush()
    return exporter
