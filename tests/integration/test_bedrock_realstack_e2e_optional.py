"""Optional live Bedrock + local real-stack end-to-end test.

This is the most production-shaped local test in the repository. It requires:

    docker compose -f docker-compose.test.yml --profile realstack up -d redis opensearch
    set BEDROCK_REALSTACK_E2E=true&& python -m pytest tests/integration/test_bedrock_realstack_e2e_optional.py -q

It uses real Bedrock Cohere embeddings to embed every sample chunk, stores those
1024-d vectors in real Docker OpenSearch, uses real LangGraph orchestration,
uses real Redis for semantic cache, and calls live Bedrock rerank/generation
adapters where enabled below.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.rag.bedrock import BedrockCitationGenerator, BedrockEmbeddingModel, BedrockReranker, resolve_rerank_model_id
from app.rag.cache import RedisSemanticCache
from app.rag.graph import GraphDeps, run_graph
from app.rag.ingestion import ingest_corpus
from app.rag.retrieval import OpenSearchBackend
from app.rag.service import DEFAULT_CORPUS_VERSION, load_users


pytestmark = pytest.mark.skipif(
    os.getenv("BEDROCK_REALSTACK_E2E", "false").lower() != "true",
    reason="set BEDROCK_REALSTACK_E2E=true to call live Bedrock and local Docker OpenSearch/Redis",
)


ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / "sample_corpus" / "manifest.json"
USERS = ROOT / "sample_requests" / "users.json"


def test_bedrock_embeddings_opensearch_langgraph_redis_generation_e2e(monkeypatch):
    pytest.importorskip("redis")
    pytest.importorskip("opensearchpy")
    pytest.importorskip("langgraph")

    monkeypatch.setenv("RAG_GRAPH_BACKEND", "langgraph")
    monkeypatch.setenv("BEDROCK_EMBEDDING_MODEL_ID", os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "eu.cohere.embed-v4:0"))

    chunks = ingest_corpus(MANIFEST)
    users = load_users(USERS)

    embedder = BedrockEmbeddingModel()
    backend = OpenSearchBackend(
        chunks,
        embedder=embedder,
        url=os.getenv("REALSTACK_OPENSEARCH_URL", "http://localhost:9200"),
        index_name=os.getenv("BEDROCK_REALSTACK_INDEX", "tax-rag-chunks-v1-bedrock-realstack-test"),
        recreate_index=True,
        timeout_seconds=60,
    )

    # Prove the corpus vectors are stored in OpenSearch using the real Bedrock
    # embedding dimension returned by the current runtime model.
    mapping = backend.client.indices.get_mapping(index=backend.index_name)
    embedding_mapping = mapping[backend.index_name]["mappings"]["properties"]["embedding"]
    assert embedding_mapping["dimension"] == embedder.dimension
    assert embedder.dimension > 0
    sample_doc = backend.client.get(index=backend.index_name, id=chunks[0].chunk_id)["_source"]
    assert len(sample_doc["embedding"]) == embedder.dimension

    cache = RedisSemanticCache(
        embedder=embedder,
        redis_url=os.getenv("REALSTACK_REDIS_URL", "redis://localhost:16379/0"),
        enabled=True,
        key_prefix="taxrag:bedrock-realstack-test",
    )
    cache.clear()

    reranker = BedrockReranker(model_id=resolve_rerank_model_id())
    generator = BedrockCitationGenerator(
        model_id=os.getenv("BEDROCK_FAST_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"),
        max_tokens=500,
    )
    deps = GraphDeps(backend=backend, embedder=embedder, reranker=reranker, answer_composer=generator)

    user = users["u_helpdesk_01"]
    query = "Can a taxpayer deduct home office expenses?"
    state = run_graph(user=user, query=query, deps=deps)

    assert state.answer is not None
    assert state.answer.abstained is False
    assert state.citations
    assert "VALIDATE_CITATIONS" in state.trace
    assert all(c.document_id != "DOC-FIOD-001" for c in state.citations)

    cache.write(
        query,
        user,
        state.answer.text,
        state.citations,
        corpus_version=DEFAULT_CORPUS_VERSION,
        embedding_model_version=embedder.model_id,
        is_cache_safe=True,
    )
    cached = cache.lookup(
        query,
        user,
        corpus_version=DEFAULT_CORPUS_VERSION,
        embedding_model_version=embedder.model_id,
    )
    assert cached is not None
    assert cached.citations

    fiod_state = run_graph(
        user=user,
        query="Summarize fraud investigation insights for home office deduction abuse.",
        deps=deps,
    )
    assert fiod_state.answer is not None
    assert fiod_state.answer.abstained is True
    assert fiod_state.citations == []
    assert all(chunk.document_id != "DOC-FIOD-001" for chunk in fiod_state.reranked_chunks)
