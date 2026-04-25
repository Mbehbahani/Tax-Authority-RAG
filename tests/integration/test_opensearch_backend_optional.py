"""Optional Stage 1B tests against a real local OpenSearch container.

These tests are skipped unless OPENSEARCH_INTEGRATION=true. Start the service with:

    docker compose -f docker-compose.test.yml --profile opensearch up -d opensearch

Then run:

    OPENSEARCH_INTEGRATION=true python -m pytest tests/integration/test_opensearch_backend_optional.py -v
"""

from __future__ import annotations

import os

import pytest

from app.rag.retrieval import OpenSearchBackend, hybrid_retrieve


pytestmark = pytest.mark.skipif(
    os.getenv("OPENSEARCH_INTEGRATION", "false").lower() != "true",
    reason="set OPENSEARCH_INTEGRATION=true and start local OpenSearch to run Stage 1B tests",
)


def _backend(corpus_chunks, embedder) -> OpenSearchBackend:
    return OpenSearchBackend(
        corpus_chunks,
        embedder=embedder,
        url=os.getenv("OPENSEARCH_URL", "http://localhost:9200"),
        index_name=os.getenv("OPENSEARCH_INDEX", "tax-rag-chunks-v1-stage1b-test"),
        recreate_index=True,
    )


def test_real_opensearch_exact_ecli_and_rbac(corpus_chunks, embedder, users):
    backend = _backend(corpus_chunks, embedder)
    hits = backend.lexical_search("Ruling ECLI:NL:HR:2023:123", users["u_inspector_01"])
    assert any(chunk.document_id == "DOC-CASE-001" for chunk, _ in hits)
    assert all(chunk.document_id != "DOC-FIOD-001" for chunk, _ in hits)


def test_real_opensearch_helpdesk_fiod_denied_before_results(corpus_chunks, embedder, users):
    backend = _backend(corpus_chunks, embedder)
    lexical = backend.lexical_search("fraud investigation indicators", users["u_helpdesk_01"])
    vector = backend.vector_search(embedder.embed("fraud investigation indicators"), users["u_helpdesk_01"])
    assert all(chunk.document_id != "DOC-FIOD-001" for chunk, _ in lexical)
    assert all(chunk.document_id != "DOC-FIOD-001" for chunk, _ in vector)


def test_real_opensearch_hybrid_retrieve_returns_citation_complete_context(corpus_chunks, embedder, users):
    backend = _backend(corpus_chunks, embedder)
    final, debug = hybrid_retrieve(
        query="Can a taxpayer deduct home office expenses?",
        user=users["u_helpdesk_01"],
        backend=backend,
        embedder=embedder,
    )
    assert final
    assert len(debug["final_chunk_ids"]) <= 8
    assert all(chunk.document_name and chunk.article and chunk.paragraph for chunk in final)
    assert all(chunk.document_id != "DOC-FIOD-001" for chunk in final)
