"""Optional Stage 3 live Bedrock-powered RAG checks.

These tests call AWS Bedrock Runtime and are skipped unless
STAGE3_LIVE_BEDROCK_RAG=true. They keep OpenSearch optional by using the same
in-memory retrieval backend, but they exercise live Bedrock generation through
the graph and citation validator.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.rag.service import build_service_from_paths


ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.skipif(
    os.getenv("STAGE3_LIVE_BEDROCK_RAG", "false").lower() != "true",
    reason="set STAGE3_LIVE_BEDROCK_RAG=true to call live Bedrock from the RAG graph",
)


def test_live_bedrock_generation_keeps_citations_authorized(monkeypatch):
    monkeypatch.setenv("BEDROCK_GENERATION_ENABLED", "true")
    monkeypatch.setenv("BEDROCK_GENERATION_MODEL_ID", os.getenv("BEDROCK_FAST_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0"))
    service, users = build_service_from_paths(
        manifest_path=ROOT / "sample_corpus" / "manifest.json",
        users_path=ROOT / "sample_requests" / "users.json",
    )
    result = service.ask(users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?")
    assert not result.abstained
    assert result.citations
    retrieved = set(result.retrieved_chunk_ids)
    assert {c["chunk_id"] for c in result.citations}.issubset(retrieved)
    assert all(c["document_id"] != "DOC-FIOD-001" for c in result.citations)
