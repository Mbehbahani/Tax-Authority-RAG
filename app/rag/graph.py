"""Deterministic CRAG / LangGraph-style state machine.

Implemented as an explicit finite-state machine rather than a LangGraph DAG so
the local PoC has zero extra dependencies. The state names, transitions, and
limits match docs/MODULE_3_AGENTIC_RAG.md and
tests/unit/langgraph_crag_state_cases.json verbatim so the same contract
transfers to LangGraph when the Bedrock integration lands.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .embeddings import EmbeddingModel
from .generation import (
    GeneratedAnswer,
    all_citations_complete,
    citations_are_subset_of_context,
    compose_answer,
    detect_prompt_injection,
)
from .models import Chunk, Citation, GraderResult, UserContext
from .retrieval import RetrievalBackend, hybrid_retrieve


# ------------------------------ config --------------------------------------

MAX_RETRIEVAL_ATTEMPTS = 2
MAX_QUERY_REWRITES = 1
MAX_HYDE_ATTEMPTS = 1
MAX_DECOMPOSITION_SUBQUERIES = 4

RELEVANT_CONFIDENCE = 0.75
AMBIGUOUS_MIN_CONFIDENCE = 0.45


# ------------------------------ state ---------------------------------------


STATES = (
    "START",
    "AUTH_CONTEXT",
    "CLASSIFY_QUERY",
    "DECOMPOSE_QUERY",
    "RETRIEVE",
    "RERANK",
    "GRADE_CONTEXT",
    "REWRITE_QUERY",
    "HYDE_QUERY",
    "GENERATE_WITH_CITATIONS",
    "VALIDATE_CITATIONS",
    "ABSTAIN",
    "END",
)


@dataclass
class RagState:
    user: UserContext
    query: str
    original_query: str
    attempts: int = 0
    rewrites_used: int = 0
    hyde_used: int = 0
    decomposed_queries: list[str] = field(default_factory=list)
    retrieved_chunks: list[Chunk] = field(default_factory=list)
    reranked_chunks: list[Chunk] = field(default_factory=list)
    grader: GraderResult | None = None
    answer: GeneratedAnswer | None = None
    citations: list[Citation] = field(default_factory=list)
    abstention_reason: str | None = None
    trace: list[str] = field(default_factory=list)
    debug: dict = field(default_factory=dict)
    injection_detected: bool = False


# ------------------------------ grader --------------------------------------


MULTI_PART_MARKERS = (" versus ", " vs ", "compare", "both ")

_STOPWORDS = frozenset(
    {
        "what",
        "when",
        "where",
        "which",
        "does",
        "can",
        "could",
        "should",
        "would",
        "the",
        "and",
        "for",
        "with",
        "about",
        "from",
        "that",
        "this",
        "have",
        "has",
        "are",
        "was",
        "were",
        "will",
        "been",
        "only",
        "summarize",
        "please",
        "give",
        "explain",
        "tell",
        "how",
        "apply",
        "applies",
        "rule",
    }
)


def _salient_tokens(query: str) -> set[str]:
    return {
        tok.lower()
        for tok in re.findall(r"[A-Za-z0-9]+", query)
        if len(tok) > 2 and tok.lower() not in _STOPWORDS
    }


def _chunk_token_universe(chunk: Chunk) -> set[str]:
    """Every token a lexical/identifier search could match against."""

    fields = [
        chunk.text,
        chunk.article,
        chunk.document_name,
        chunk.document_id,
        chunk.ecli or "",
        " ".join(chunk.section_path or ()),
    ]
    tokens: set[str] = set()
    for field in fields:
        for tok in re.findall(r"[A-Za-z0-9]+", field):
            tokens.add(tok.lower())
    return tokens


def grade_context(query: str, chunks: list[Chunk], *, user: UserContext | None = None) -> GraderResult:
    """Return Relevant / Ambiguous / Irrelevant based on token coverage and version conflicts.

    Coverage: fraction of salient query tokens that appear in at least one
    authorized chunk (including identifier fields like ECLI/document_id). This
    correctly marks fraud queries Irrelevant for helpdesk (no "fraud" token in
    authorized chunks) and ECLI queries Relevant for inspector/legal (tokens
    match the case-law chunk's ``ecli`` field).
    """

    # Version-conflict detection runs first.
    year_match = re.search(r"tax year (\d{4})", query.lower())
    if year_match and chunks:
        year = year_match.group(1)
        any_applies = False
        for chunk in chunks:
            if not chunk.effective_from:
                continue
            if chunk.effective_from <= f"{year}-12-31" and (
                chunk.effective_to is None or chunk.effective_to >= f"{year}-01-01"
            ):
                if chunk.version and chunk.version.endswith("current"):
                    any_applies = True
                    break
                if chunk.effective_from.startswith(year):
                    any_applies = True
                    break
        if not any_applies:
            return GraderResult(
                label="Ambiguous",
                confidence=0.5,
                reasons=[f"no authorized chunk applies to tax year {year}"],
                missing_evidence=["effective_date_match"],
                required_action="decompose_or_clarify_effective_date",
            )

    if not chunks:
        return GraderResult(
            label="Irrelevant",
            confidence=0.0,
            reasons=["no authorized context"],
            missing_evidence=["authorized_context"],
            required_action="rewrite_or_abstain_after_retry",
        )

    salient = _salient_tokens(query)
    if not salient:
        return GraderResult(
            label="Irrelevant",
            confidence=0.0,
            reasons=["no salient query tokens"],
            required_action="rewrite_or_abstain_after_retry",
        )

    corpus_tokens: set[str] = set()
    for chunk in chunks:
        corpus_tokens.update(_chunk_token_universe(chunk))

    matched = salient & corpus_tokens
    coverage = len(matched) / len(salient)

    # Count how many retrieved chunks actually contain at least two salient
    # tokens - this prevents a single shared stop-like word from inflating the
    # score for off-topic retrievals.
    strong_chunks = 0
    for chunk in chunks:
        chunk_tokens = _chunk_token_universe(chunk)
        if len(salient & chunk_tokens) >= 2:
            strong_chunks += 1
    strong_ratio = strong_chunks / len(chunks)

    multi_part = any(m in query.lower() for m in MULTI_PART_MARKERS)

    if coverage >= 0.75 and strong_ratio >= 0.3 and not multi_part:
        return GraderResult(
            label="Relevant",
            confidence=min(0.99, 0.6 + coverage * 0.4),
            reasons=[f"coverage={coverage:.2f} strong_ratio={strong_ratio:.2f}"],
            required_action="generate_with_citations",
        )
    if coverage >= 0.5 or multi_part:
        return GraderResult(
            label="Ambiguous",
            confidence=0.55,
            reasons=["partial coverage or multi-part query"],
            missing_evidence=["sharper_query"],
            required_action="decompose_or_clarify",
        )
    missing = sorted(salient - matched)
    return GraderResult(
        label="Irrelevant",
        confidence=max(0.0, coverage),
        reasons=[f"coverage={coverage:.2f} missing={missing[:5]}"],
        missing_evidence=missing,
        required_action="rewrite_or_abstain_after_retry",
    )


# ------------------------------ transformations -----------------------------


def rewrite_query(original: str) -> str:
    """Bounded rewrite: strip stopwords and add a legal-term anchor."""

    lowered = original.lower()
    for drop in ("please", "can you", "could you", "kindly", "summarize"):
        lowered = lowered.replace(drop, "")
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return f"legal basis for {lowered}".strip()


def hyde_expand(original: str) -> str:
    """One-shot hypothetical document expansion used only for retrieval."""

    return (
        f"Hypothetical legal paragraph describing the requirements, conditions, "
        f"and documentation duties that apply to: {original}"
    )


def decompose_query(original: str, *, limit: int = MAX_DECOMPOSITION_SUBQUERIES) -> list[str]:
    """Split a multi-part question on conjunctions and "after <ref>" clauses.

    Deterministic heuristics only; a real implementation would call a small
    classifier. The output is bounded to avoid runaway retrievals.
    """

    parts = re.split(r"\band\b|\b;\b|\bas well as\b|\?", original, flags=re.IGNORECASE)
    cleaned = [p.strip(" .?,") for p in parts if p and p.strip(" .?,")]
    if len(cleaned) <= 1:
        return [original]
    return cleaned[:limit]


# ------------------------------ state machine -------------------------------


@dataclass
class GraphDeps:
    backend: RetrievalBackend
    embedder: EmbeddingModel
    grader: Callable[[str, list[Chunk], UserContext | None], GraderResult] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.grader is None:
            self.grader = lambda q, c, u=None: grade_context(q, c, user=u)


def _retrieve(state: RagState, deps: GraphDeps) -> None:
    state.attempts += 1
    final_context, debug = hybrid_retrieve(
        query=state.query,
        user=state.user,
        backend=deps.backend,
        embedder=deps.embedder,
    )
    state.retrieved_chunks = final_context
    state.reranked_chunks = final_context
    state.debug.setdefault("retrievals", []).append(debug)


def _generate(state: RagState) -> None:
    state.answer = compose_answer(state.query, state.reranked_chunks)
    state.citations = state.answer.citations


def _validate_citations(state: RagState) -> str:
    answer = state.answer
    if answer is None or answer.abstained:
        state.abstention_reason = answer.abstention_reason if answer else "no_answer"
        return "ABSTAIN"
    if not all_citations_complete(answer.citations):
        state.abstention_reason = "citation_incomplete"
        return "ABSTAIN"
    if not citations_are_subset_of_context(answer.citations, state.reranked_chunks):
        state.abstention_reason = "citation_not_in_authorized_context"
        return "ABSTAIN"
    return "END"


def run_graph(
    *,
    user: UserContext,
    query: str,
    deps: GraphDeps,
) -> RagState:
    """Execute the deterministic CRAG state machine.

    Returns the final state. ``state.trace`` records every transition so tests
    can assert exact state orderings, and abstention reasons are exposed on
    ``state.abstention_reason`` for audit.
    """

    state = RagState(user=user, query=query, original_query=query)
    state.trace.append("START")

    # AUTH_CONTEXT
    state.trace.append("AUTH_CONTEXT")

    # CLASSIFY_QUERY - also the place where we block prompt injection before
    # it can influence any downstream stage.
    state.trace.append("CLASSIFY_QUERY")
    if detect_prompt_injection(query):
        state.injection_detected = True
        state.abstention_reason = "prompt_injection_detected"
        state.trace.append("ABSTAIN")
        state.answer = GeneratedAnswer(text="", citations=[], abstained=True, abstention_reason="prompt_injection_detected")
        state.trace.append("END")
        return state

    # Optional DECOMPOSE_QUERY
    sub_queries = decompose_query(query)
    if len(sub_queries) > 1:
        state.decomposed_queries = sub_queries
        state.trace.append("DECOMPOSE_QUERY")

    # Retrieval loop with bounded corrections.
    while state.attempts < MAX_RETRIEVAL_ATTEMPTS:
        state.trace.append("RETRIEVE")
        _retrieve(state, deps)
        state.trace.append("RERANK")

        state.trace.append("GRADE_CONTEXT")
        state.grader = deps.grader(state.query, state.reranked_chunks, state.user)

        label = state.grader.label

        if label == "Relevant" and state.reranked_chunks:
            break

        if label == "Ambiguous" and state.attempts < MAX_RETRIEVAL_ATTEMPTS:
            # Bounded decomposition: we already expanded sub_queries; try HyDE
            # expansion as the second correction signal.
            if state.hyde_used < MAX_HYDE_ATTEMPTS:
                state.query = hyde_expand(state.query)
                state.hyde_used += 1
                state.trace.append("HYDE_QUERY")
                continue
            state.abstention_reason = "ambiguous_evidence_after_correction"
            break

        if label == "Irrelevant" and state.attempts < MAX_RETRIEVAL_ATTEMPTS:
            if state.rewrites_used < MAX_QUERY_REWRITES:
                state.query = rewrite_query(state.query)
                state.rewrites_used += 1
                state.trace.append("REWRITE_QUERY")
                continue
            if state.hyde_used < MAX_HYDE_ATTEMPTS:
                state.query = hyde_expand(state.query)
                state.hyde_used += 1
                state.trace.append("HYDE_QUERY")
                continue
            state.abstention_reason = "irrelevant_after_corrections"
            break

        # Retry budget exhausted while still Irrelevant/Ambiguous.
        state.abstention_reason = state.abstention_reason or "retry_budget_exhausted"
        break

    # Terminal transition.
    grader_label = state.grader.label if state.grader else "Irrelevant"
    if grader_label != "Relevant" or not state.reranked_chunks:
        state.trace.append("ABSTAIN")
        state.answer = GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason=state.abstention_reason or "grader_not_relevant",
        )
        state.trace.append("END")
        return state

    state.trace.append("GENERATE_WITH_CITATIONS")
    _generate(state)

    state.trace.append("VALIDATE_CITATIONS")
    final = _validate_citations(state)
    if final == "ABSTAIN":
        state.trace.append("ABSTAIN")
        state.answer = GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason=state.abstention_reason or "citation_validation_failed",
        )
    state.trace.append("END")
    return state
