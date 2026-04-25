"""Optional live Stage 4 Bedrock rerank/embed and OpenSearch quality checks."""

from __future__ import annotations

import os

import pytest

from app.rag.bedrock import BedrockEmbeddingModel, BedrockReranker, make_bedrock_runtime_client, resolve_rerank_model_id
from app.rag.evaluation import compare_retrieval_quality
from app.rag.retrieval import InMemoryOpenSearchBackend


pytestmark = pytest.mark.skipif(
    os.getenv("STAGE4_LIVE_RETRIEVAL_EVAL", "false").lower() != "true",
    reason="set STAGE4_LIVE_RETRIEVAL_EVAL=true to run live Bedrock embedding/rerank checks",
)


def test_live_cohere_embed_v4_retrieval_quality_against_deterministic(corpus_chunks, backend, embedder, users):
    client = make_bedrock_runtime_client()
    cohere_embedder = BedrockEmbeddingModel(client=client)
    cohere_backend = InMemoryOpenSearchBackend(corpus_chunks, embedder=cohere_embedder)
    comparison = compare_retrieval_quality(
        query="Can a taxpayer deduct home office expenses?",
        user=users["u_helpdesk_01"],
        baseline_backend=backend,
        baseline_embedder=embedder,
        candidate_backend=cohere_backend,
        candidate_embedder=cohere_embedder,
    )
    assert comparison["candidate_context_count"] > 0
    assert comparison["candidate_has_complete_citations"] is True


def test_live_cohere_rerank_runtime_probe(corpus_chunks):
    client = make_bedrock_runtime_client()
    reranker = BedrockReranker(client=client, model_id=resolve_rerank_model_id())
    assert reranker.probe() is True
