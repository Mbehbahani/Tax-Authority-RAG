"""Deterministic tests for RRF fusion and the reranker caps."""

from __future__ import annotations

from app.rag.models import Chunk
from app.rag.retrieval import (
    DEFAULT_RERANK_MAX,
    FusionResult,
    reciprocal_rank_fusion,
    rerank,
    take_candidates,
    take_with_complete_citations,
)


def _fake_chunk(chunk_id: str, text: str = "t", *, article: str | None = None, paragraph: str | None = None) -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id=chunk_id,
        document_name=f"Doc {chunk_id}",
        source_type="legislation",
        text=text,
        article=article or chunk_id,
        paragraph=paragraph or "1",
    )


def test_rrf_combines_exact_and_semantic_signals():
    bm25 = [_fake_chunk("DOC-CASE-001"), _fake_chunk("DOC-LEG-001"), _fake_chunk("DOC-POL-001")]
    vec = [_fake_chunk("DOC-LEG-001"), _fake_chunk("DOC-CASE-001"), _fake_chunk("DOC-ELRN-001")]
    fused = reciprocal_rank_fusion([bm25, vec])
    top_two = {r.chunk.chunk_id for r in fused[:2]}
    assert {"DOC-CASE-001", "DOC-LEG-001"} == top_two


def test_rrf_score_is_deterministic_and_stable():
    bm25 = [_fake_chunk("A"), _fake_chunk("B")]
    vec = [_fake_chunk("B"), _fake_chunk("A")]
    first = reciprocal_rank_fusion([bm25, vec])
    second = reciprocal_rank_fusion([bm25, vec])
    assert [r.chunk.chunk_id for r in first] == [r.chunk.chunk_id for r in second]


def test_rerank_caps_candidate_count():
    fused = [
        FusionResult(_fake_chunk(f"C{i}"), rrf_score=1.0 / (60 + i), lexical_rank=i, vector_rank=None)
        for i in range(1, 100)
    ]
    candidates = take_candidates(fused, limit=80)
    assert len(candidates) == 80
    reranked = rerank("legal home office deduction", candidates, max_candidates=DEFAULT_RERANK_MAX)
    assert len(reranked) == DEFAULT_RERANK_MAX


def test_take_final_top_n_deduplicates_historical_versions():
    current = Chunk(
        chunk_id="c1",
        document_id="DOC-LEG-001",
        document_name="Current Act",
        source_type="legislation",
        text="current",
        article="3.12",
        paragraph="1",
        version="2024-current",
    )
    historical = Chunk(
        chunk_id="h1",
        document_id="DOC-LEG-2022-001",
        document_name="Historical Act",
        source_type="legislation",
        text="historical",
        article="3.12",
        paragraph="1",
        effective_from="2022-01-01",
        effective_to="2022-12-31",
        version="2022-historical",
    )
    reranked = [
        FusionResult(historical, rrf_score=0.5, lexical_rank=1, vector_rank=None),
        FusionResult(current, rrf_score=0.4, lexical_rank=2, vector_rank=None),
    ]
    final = take_with_complete_citations(reranked, limit=5)
    ids = [c.chunk_id for c in final]
    assert "c1" in ids
    assert "h1" not in ids


def test_final_top_n_honours_limit():
    chunks = [_fake_chunk(f"C{i}") for i in range(1, 30)]
    reranked = [FusionResult(c, rrf_score=1.0 - 0.01 * i, lexical_rank=i, vector_rank=None) for i, c in enumerate(chunks)]
    final = take_with_complete_citations(reranked, limit=8)
    assert len(final) == 8
