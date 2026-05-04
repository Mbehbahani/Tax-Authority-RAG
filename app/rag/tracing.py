"""Optional span-level pipeline tracing via Langfuse.

Design goals
------------
- Zero business-logic changes: all tracing calls are optional no-ops.
- Zero overhead when ENABLE_LANGFUSE=false: ``_NullTracer`` short-circuits
  everything — no allocations beyond a single module-level singleton comparison.
- No raw document text, query text, or PII are logged.  Only counts, hashes,
  scores, decisions, and timing are sent to Langfuse.
- Thread-safe: one ``PipelineTracer`` per request; a module-level lazily
  initialised client avoids per-request auth overhead.

Span hierarchy (flat — all spans are direct children of the root trace)
----------------------------------------------------------------------
::

    tax_rag.request               ← root trace
      auth_context                  role, clearance, need_to_know_count
      query_classification          query_hash → injection_detected, sub_query_count
      retrieval_bm25                query_hash, top_k → hit_count, top_score
      retrieval_vector              query_hash, embedding_dim, top_k → hit_count, top_score
      rrf_fusion                    lexical_count, vector_count → fused_count, top_rrf_score
      rerank                        candidate_count → reranked_count, final_count, reranker
      context_grade                 chunk_count, attempt → label, confidence, required_action
      query_rewrite (if used)       attempt → new_query_hash
      hyde (if used)                attempt → new_query_hash
      generation                    context_chunk_count → abstained, citation_count
      citation_validation           citation_count → passed
      abstention_decision (if abs.) reason → final_decision

Environment variables (shared with ``observability_langfuse``)
--------------------------------------------------------------
  ENABLE_LANGFUSE, LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from .observability_langfuse import _langfuse_importable, is_langfuse_enabled


# ---------------------------------------------------------------------------
# Null objects — zero overhead when tracing is disabled
# ---------------------------------------------------------------------------


class _NullSpan:
    """No-op span returned when tracing is disabled."""

    __slots__ = ()

    def end(self, **kwargs: Any) -> None:
        pass

    def update(self, **kwargs: Any) -> None:
        pass

    def __enter__(self) -> "_NullSpan":
        return self

    def __exit__(self, *args: Any) -> bool:
        return False


_SINGLETON_NULL_SPAN = _NullSpan()


class _NullTracer:
    """No-op tracer — all methods are no-ops, returns a singleton null span."""

    enabled: bool = False

    def span(self, name: str, **kwargs: Any) -> _NullSpan:
        return _SINGLETON_NULL_SPAN

    def generation(self, name: str, **kwargs: Any) -> _NullSpan:
        return _SINGLETON_NULL_SPAN

    def end(self, **kwargs: Any) -> None:
        pass

    def flush(self) -> None:
        pass


_NULL_TRACER: _NullTracer = _NullTracer()


# ---------------------------------------------------------------------------
# Active span handle
# ---------------------------------------------------------------------------


class _SpanHandle:
    """Wraps a Langfuse span/observation; records latency automatically on end().

    Idempotent: calling ``end()`` more than once is safe — only the first call
    is forwarded to Langfuse.
    """

    __slots__ = ("_span", "_start", "_active", "_ended")

    def __init__(self, span: Any) -> None:
        self._span = span
        self._start = time.monotonic()
        self._active = True
        self._ended = False

    @classmethod
    def inactive(cls) -> "_SpanHandle":
        """Return a disabled handle that does nothing — used as a safe fallback."""
        h: _SpanHandle = object.__new__(cls)
        h._span = None
        h._start = time.monotonic()
        h._active = False
        h._ended = True
        return h

    def end(
        self,
        *,
        output: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """End the span, recording elapsed time in metadata.latency_seconds."""
        if not self._active or self._ended:
            return
        self._ended = True
        elapsed = round(time.monotonic() - self._start, 4)
        try:
            m = {**(metadata or {}), "latency_seconds": elapsed}
            self._span.update(output=output or {}, metadata=m)
            self._span.end()
        except Exception:
            pass

    def update(self, **kwargs: Any) -> None:
        if not self._active or self._span is None:
            return
        try:
            self._span.update(**kwargs)
        except Exception:
            pass

    def __enter__(self) -> "_SpanHandle":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        output = {"error": str(exc_val)} if exc_type else None
        self.end(output=output)
        return False


# ---------------------------------------------------------------------------
# Active pipeline tracer
# ---------------------------------------------------------------------------


class PipelineTracer:
    """Wraps a single RAG request as a Langfuse Trace with child span observations.

    One ``PipelineTracer`` per request.  Call ``flush()`` at the end of the
    request to ensure all queued events reach Langfuse.

    Instantiate via :func:`get_pipeline_tracer` which returns a ``_NullTracer``
    automatically when Langfuse is not enabled.

    Usage::

        tracer = get_pipeline_tracer(
            request_id="req-uuid",
            sanitised_role="helpdesk_abc12345",
            query="...",
        )
        s = tracer.span("auth_context", input_data={"role": "helpdesk"})
        s.end(output={"rbac_filter_applied": True})
        tracer.flush()
    """

    enabled: bool = True

    def __init__(
        self,
        client: Any,
        *,
        trace_name: str,
        sanitised_user_id: str,
        metadata: dict[str, Any],
    ) -> None:
        self._client = client
        self._trace: Any = None
        self._trace_id: str = ""
        try:
            self._trace_id = client.create_trace_id(seed=trace_name)
            self._trace = client.start_observation(
                trace_context={"trace_id": self._trace_id},
                name=trace_name,
                input=None,
                output=None,
                metadata=metadata,
            )
        except Exception:
            self._trace_id = ""
            pass

    @property
    def trace_id(self) -> str:
        return getattr(self._trace, "trace_id", self._trace_id) if self._trace else self._trace_id

    def span(
        self,
        name: str,
        *,
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _SpanHandle:
        """Create a child span on the root trace."""
        if self._trace is None:
            return _SpanHandle.inactive()
        try:
            s = self._trace.start_observation(
                name=name,
                input=input_data or {},
                metadata=metadata or {},
                as_type="span",
            )
            return _SpanHandle(s)
        except Exception:
            return _SpanHandle.inactive()

    def generation(
        self,
        name: str,
        *,
        model: str = "",
        input_data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> _SpanHandle:
        """Create a generation-type observation (LLM call stages).

        Only safe metadata (counts, hashes, decisions) is included — never
        raw prompt text or completion text.
        """
        if self._trace is None:
            return _SpanHandle.inactive()
        try:
            s = self._trace.start_observation(
                name=name,
                as_type="generation",
                input=input_data or {},
                metadata={**(metadata or {}), "model": model},
                model=model or None,
            )
            return _SpanHandle(s)
        except Exception:
            return _SpanHandle.inactive()

    def end(self, *, output: dict[str, Any] | None = None) -> None:
        """Update the root trace with a final output summary."""
        if self._trace is None:
            return
        try:
            self._trace.update(output=output or {})
        except Exception:
            pass

    def flush(self) -> None:
        """Flush all queued Langfuse events — call once at end of request."""
        try:
            self._client.flush()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Module-level lazy shared client
# ---------------------------------------------------------------------------

_SHARED_CLIENT: Any = None
_CLIENT_INITIALIZED: bool = False


def _get_shared_client() -> Any:
    """Return the module-level Langfuse client, initialising it lazily on first call."""
    global _SHARED_CLIENT, _CLIENT_INITIALIZED
    if _CLIENT_INITIALIZED:
        return _SHARED_CLIENT
    _CLIENT_INITIALIZED = True
    if not is_langfuse_enabled():
        return None
    try:
        from langfuse import Langfuse  # noqa: PLC0415

        _SHARED_CLIENT = Langfuse(
            public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
            secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""),
            host=os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com"),
        )
    except Exception:
        _SHARED_CLIENT = None
    return _SHARED_CLIENT


def _reset_shared_client() -> None:
    """Reset the module-level client — call this in tests that need a fresh state."""
    global _SHARED_CLIENT, _CLIENT_INITIALIZED
    _SHARED_CLIENT = None
    _CLIENT_INITIALIZED = False


# ---------------------------------------------------------------------------
# Safe attribute helpers
# ---------------------------------------------------------------------------


def _query_hash(query: str) -> str:
    """Return a 16-char SHA-256 hex prefix of the query — never the raw text."""
    return hashlib.sha256(query.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def get_pipeline_tracer(
    *,
    request_id: str,
    sanitised_role: str,
    query: str,
    extra_metadata: dict[str, Any] | None = None,
) -> "PipelineTracer | _NullTracer":
    """Return an active ``PipelineTracer`` when Langfuse is enabled, else ``_NullTracer``.

    Parameters
    ----------
    request_id:
        Opaque correlation ID (UUID / request ID from the HTTP layer).
    sanitised_role:
        From :func:`~app.rag.observability_langfuse._sanitise_role` — role + hash prefix.
    query:
        Raw query text; only a SHA-256 hash prefix is logged, never the text.
    extra_metadata:
        Safe additional metadata (no raw document text, no PII).
    """
    client = _get_shared_client()
    if client is None:
        return _NULL_TRACER

    metadata: dict[str, Any] = {
        "request_id": request_id,
        "query_hash": _query_hash(query),
        **(extra_metadata or {}),
    }
    return PipelineTracer(
        client,
        trace_name="tax_rag.request",
        sanitised_user_id=sanitised_role,
        metadata=metadata,
    )
