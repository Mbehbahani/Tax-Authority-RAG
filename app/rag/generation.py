"""Deterministic extractive answer composer.

For the local PoC we do not call Bedrock. Instead the composer produces one
atomic claim per cited chunk by quoting the chunk verbatim, with a citation
made directly from the chunk's authorized metadata. This satisfies the
zero-hallucination constraint exactly because:

* every claim is a literal quote of an authorized chunk;
* every claim has an exact citation (document_name, article, paragraph);
* every generated citation's chunk_id is by construction a member of the
  authorized retrieved context.

The production version replaces this module with a guarded Bedrock call that
obeys the same contract; tests target the same assertions in both modes.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Chunk, Citation


PROMPT_INJECTION_MARKERS = (
    "ignore all access rules",
    "ignore access rules",
    "ignore previous instructions",
    "reveal the fiod",
    "bypass access",
    "disregard rbac",
    "override role",
)


@dataclass
class GeneratedAnswer:
    text: str
    citations: list[Citation]
    abstained: bool
    abstention_reason: str | None = None


def detect_prompt_injection(query: str) -> bool:
    low = query.lower()
    return any(marker in low for marker in PROMPT_INJECTION_MARKERS)


def compose_answer(
    query: str,
    authorized_context: list[Chunk],
    *,
    max_claims: int = 4,
) -> GeneratedAnswer:
    """Build an answer by stringing cited quotes together.

    Caller guarantees every ``authorized_context`` chunk has already passed
    RBAC. We still defensively reject empty/incomplete citation chunks.
    """

    if detect_prompt_injection(query):
        return GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason="prompt_injection_detected",
        )

    if not authorized_context:
        return GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason="no_authorized_context",
        )

    citations: list[Citation] = []
    claims: list[str] = []
    for chunk in authorized_context[:max_claims]:
        cite = Citation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            article=chunk.article,
            paragraph=chunk.paragraph,
        )
        if not cite.is_complete():
            continue
        claim = f'"{chunk.text.strip()}" {cite.format()}'
        claims.append(claim)
        citations.append(cite)

    if not claims:
        return GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason="no_citation_complete_chunks",
        )

    text = "\n".join(claims)
    return GeneratedAnswer(text=text, citations=citations, abstained=False)


def citations_are_subset_of_context(
    citations: list[Citation], context: list[Chunk]
) -> bool:
    authorized_ids = {c.chunk_id for c in context}
    return all(c.chunk_id in authorized_ids for c in citations)


def all_citations_complete(citations: list[Citation]) -> bool:
    return bool(citations) and all(c.is_complete() for c in citations)
