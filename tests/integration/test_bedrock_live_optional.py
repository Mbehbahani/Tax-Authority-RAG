"""Optional Stage 2 live AWS Bedrock compatibility checks.

Skipped unless BEDROCK_LIVE_INTEGRATION=true. These tests validate catalog and
minimal runtime request contracts only; they do not replace the deterministic
offline RAG tests and they do not deploy infrastructure.
"""

from __future__ import annotations

import os

import pytest

from app.rag.bedrock import (
    DEFAULT_BEDROCK_REGION,
    DEFAULT_EMBED_MODEL_ID,
    DEFAULT_FAST_MODEL_ID,
    EXPECTED_STAGE2_MODEL_IDS,
    BedrockEmbeddingModel,
    check_model_catalog_availability,
    make_bedrock_catalog_client,
    make_bedrock_runtime_client,
)


pytestmark = pytest.mark.skipif(
    os.getenv("BEDROCK_LIVE_INTEGRATION", "false").lower() != "true",
    reason="set BEDROCK_LIVE_INTEGRATION=true to call live AWS Bedrock APIs",
)


def test_live_bedrock_catalog_lists_stage2_models():
    client = make_bedrock_catalog_client(region_name=DEFAULT_BEDROCK_REGION)
    results = check_model_catalog_availability(client, expected_model_ids=EXPECTED_STAGE2_MODEL_IDS)
    missing = [result.model_id for result in results if not result.listed]
    assert not missing


def test_live_bedrock_embedding_minimal_invocation():
    client = make_bedrock_runtime_client(region_name=DEFAULT_BEDROCK_REGION)
    embedder = BedrockEmbeddingModel(client=client, model_id=DEFAULT_EMBED_MODEL_ID)
    vector = embedder.embed("home office deduction")
    assert vector
    assert all(isinstance(value, float) for value in vector)


def test_live_bedrock_fast_model_minimal_invocation():
    client = make_bedrock_runtime_client(region_name=DEFAULT_BEDROCK_REGION)
    response = client.invoke_model(
        modelId=DEFAULT_FAST_MODEL_ID,
        body=(
            '{"anthropic_version":"bedrock-2023-05-31","max_tokens":20,'
            '"temperature":0,"messages":[{"role":"user","content":[{"type":"text",'
            '"text":"Return only the word ready."}]}]}'
        ),
        contentType="application/json",
        accept="application/json",
    )
    assert response.get("body") is not None
