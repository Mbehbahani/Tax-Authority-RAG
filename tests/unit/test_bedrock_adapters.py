"""Offline Stage 2 tests for Bedrock request/response adapters."""

from __future__ import annotations

import json

from app.rag.bedrock import (
    BedrockCitationGenerator,
    BedrockEmbeddingModel,
    BedrockReranker,
    build_citation_prompt,
    check_model_catalog_availability,
    parse_claude_citation_response,
)
from app.rag.models import Chunk
from app.rag.retrieval import FusionResult


class _Body:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _RuntimeClient:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []

    def invoke_model(self, *, modelId: str, body: str, contentType: str, accept: str) -> dict:
        self.calls.append(
            {
                "modelId": modelId,
                "body": json.loads(body),
                "contentType": contentType,
                "accept": accept,
            }
        )
        return {"body": _Body(self.payload)}


class _CatalogClient:
    def list_foundation_models(self) -> dict:
        return {
            "modelSummaries": [
                {"modelId": "cohere.embed-v4:0", "providerName": "Cohere", "modelName": "Embed v4"},
                {"modelId": "anthropic.claude-3-7-sonnet-20250219-v1:0", "providerName": "Anthropic"},
            ]
        }

    def list_inference_profiles(self) -> dict:
        return {
            "inferenceProfileSummaries": [
                {"inferenceProfileId": "eu.cohere.embed-v4:0", "inferenceProfileName": "EU Cohere Embed v4"}
            ]
        }


def _chunk(chunk_id: str = "c1") -> Chunk:
    return Chunk(
        chunk_id=chunk_id,
        document_id="DOC-LEG-001",
        document_name="Synthetic Income Tax Act 2024",
        source_type="legislation",
        text="Home office expenses are deductible when statutory criteria are met.",
        article="3.12",
        paragraph="1",
        allowed_roles=["helpdesk"],
    )


def test_catalog_availability_reports_listed_and_missing_models():
    results = check_model_catalog_availability(
        _CatalogClient(),
        expected_model_ids=("cohere.embed-v4:0", "eu.cohere.embed-v4:0", "missing.model"),
    )
    assert results[0].listed is True
    assert results[0].provider == "Cohere"
    assert results[1].listed is True
    assert results[1].model_name == "EU Cohere Embed v4"
    assert results[2].listed is False


def test_cohere_embedding_payload_and_response_shape():
    client = _RuntimeClient({"embeddings": {"float": [[0.1, 0.2, 0.3]]}})
    model = BedrockEmbeddingModel(client=client, model_id="eu.cohere.embed-v4:0", dimension=3)
    assert model.embed("home office") == [0.1, 0.2, 0.3]
    call = client.calls[0]
    assert call["modelId"] == "eu.cohere.embed-v4:0"
    assert call["body"]["texts"] == ["home office"]
    assert call["body"]["input_type"] == "search_document"
    assert call["body"]["embedding_types"] == ["float"]


def test_titan_embedding_payload_and_response_shape():
    client = _RuntimeClient({"embedding": [0.4, 0.5]})
    model = BedrockEmbeddingModel(client=client, model_id="amazon.titan-embed-text-v2:0", dimension=2)
    assert model.embed("home office") == [0.4, 0.5]
    assert client.calls[0]["body"] == {"inputText": "home office"}


def test_cohere_reranker_reorders_candidates_by_response_index():
    c1 = _chunk("c1")
    c2 = _chunk("c2")
    client = _RuntimeClient({"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]})
    reranker = BedrockReranker(client=client)
    rows = [FusionResult(c1, 0.01), FusionResult(c2, 0.01)]
    ordered = reranker.rerank("home office", rows)
    assert [row.chunk.chunk_id for row in ordered] == ["c2", "c1"]
    assert client.calls[0]["modelId"] == "cohere.rerank-v3-5:0"
    assert client.calls[0]["body"]["query"] == "home office"


def test_citation_prompt_contains_only_authorized_context_fields():
    prompt = build_citation_prompt("Can I deduct?", [_chunk()])
    assert "Can I deduct?" in prompt
    assert "DOC-LEG-001" in prompt
    assert "chunk_id" in prompt


def test_parse_claude_response_requires_authorized_chunk_membership():
    payload = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "answer": "Allowed",
                        "claims": [{"text": "Deductible if criteria are met.", "chunk_id": "c1"}],
                        "abstained": False,
                        "abstention_reason": None,
                    }
                ),
            }
        ]
    }
    answer = parse_claude_citation_response(payload, [_chunk("c1")])
    assert answer is not None
    assert not answer.abstained
    assert answer.citations[0].document_id == "DOC-LEG-001"


def test_parse_claude_response_rejects_unretrieved_chunk_id():
    payload = {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "answer": "Leak",
                        "claims": [{"text": "Restricted claim.", "chunk_id": "missing"}],
                        "abstained": False,
                    }
                ),
            }
        ]
    }
    assert parse_claude_citation_response(payload, [_chunk("c1")]) is None


def test_bedrock_generator_falls_back_to_deterministic_safe_answer_on_bad_json():
    client = _RuntimeClient({"content": [{"type": "text", "text": "not-json"}]})
    generator = BedrockCitationGenerator(client=client)
    answer = generator.compose("Can a taxpayer deduct home office expenses?", [_chunk("c1")])
    assert not answer.abstained
    assert answer.citations[0].chunk_id == "c1"
    assert client.calls[0]["modelId"] == "eu.anthropic.claude-3-7-sonnet-20250219-v1:0"
