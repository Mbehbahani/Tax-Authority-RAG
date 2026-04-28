"""Stage 2 Bedrock compatibility adapters.

The local PoC remains deterministic by default. This module adds opt-in
Bedrock Runtime and Bedrock catalog integration behind small interfaces so
Stage 2 can validate model availability and request/response contracts without
changing the RAG graph or weakening zero-hallucination guarantees.
"""

from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

from .generation import GeneratedAnswer, compose_answer
from .models import Chunk, Citation
from .retrieval import FusionResult


def resolve_runtime_model_id(model_id: str) -> str:
    """Map catalog/base IDs to invocation-ready EU inference profiles when needed."""

    runtime_overrides = {
        "cohere.embed-v4:0": "eu.cohere.embed-v4:0",
        "anthropic.claude-3-haiku-20240307-v1:0": "eu.anthropic.claude-haiku-4-5-20251001-v1:0",
        "anthropic.claude-3-7-sonnet-20250219-v1:0": "eu.anthropic.claude-3-7-sonnet-20250219-v1:0",
    }
    return runtime_overrides.get(model_id, model_id)


DEFAULT_BEDROCK_REGION = os.getenv("BEDROCK_REGION") or os.getenv("AWS_REGION", "eu-central-1")
DEFAULT_EMBED_MODEL_ID = resolve_runtime_model_id(os.getenv("BEDROCK_EMBEDDING_MODEL_ID", "eu.cohere.embed-v4:0"))
DEFAULT_FALLBACK_EMBED_MODEL_ID = os.getenv(
    "BEDROCK_FALLBACK_EMBEDDING_MODEL_ID", "amazon.titan-embed-text-v2:0"
)
DEFAULT_GENERATION_MODEL_ID = resolve_runtime_model_id(
    os.getenv("BEDROCK_GENERATION_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0")
)
DEFAULT_FAST_MODEL_ID = resolve_runtime_model_id(
    os.getenv("BEDROCK_FAST_MODEL_ID", "eu.anthropic.claude-haiku-4-5-20251001-v1:0")
)
DEFAULT_JUDGE_MODEL_ID = resolve_runtime_model_id(
    os.getenv("BEDROCK_JUDGE_MODEL_ID", "eu.anthropic.claude-3-7-sonnet-20250219-v1:0")
)
DEFAULT_RERANK_MODEL_ID = os.getenv("BEDROCK_RERANK_MODEL_ID", "cohere.rerank-v3-5:0")
DEFAULT_RERANK_INFERENCE_PROFILE_ID = os.getenv("BEDROCK_RERANK_INFERENCE_PROFILE_ID", "")
EXPECTED_STAGE2_MODEL_IDS = (
    DEFAULT_EMBED_MODEL_ID,
    DEFAULT_FALLBACK_EMBED_MODEL_ID,
    DEFAULT_GENERATION_MODEL_ID,
    DEFAULT_FAST_MODEL_ID,
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_RERANK_MODEL_ID,
)


class BedrockRuntimeLike(Protocol):
    def invoke_model(self, *, modelId: str, body: str, contentType: str, accept: str) -> dict[str, Any]: ...


class BedrockCatalogLike(Protocol):
    def list_foundation_models(self, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class BedrockModelAvailability:
    model_id: str
    listed: bool
    provider: str | None = None
    model_name: str | None = None


def make_bedrock_runtime_client(*, region_name: str = DEFAULT_BEDROCK_REGION):
    """Create a boto3 Bedrock Runtime client only when the caller opts in."""

    try:
        import boto3
        from botocore.exceptions import ProfileNotFound
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("boto3 is required for live Bedrock runtime checks") from exc
    try:
        return boto3.client("bedrock-runtime", region_name=region_name)
    except ProfileNotFound:
        # Some local .env files may define a documentation-only AWS_PROFILE that
        # is not configured on the machine. Fall back to the default AWS CLI
        # credential chain, which is the path validated by aws sts checks.
        os.environ.pop("AWS_PROFILE", None)
        return boto3.client("bedrock-runtime", region_name=region_name)


def make_bedrock_catalog_client(*, region_name: str = DEFAULT_BEDROCK_REGION):
    """Create a boto3 Bedrock control-plane client only when the caller opts in."""

    try:
        import boto3
        from botocore.exceptions import ProfileNotFound
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("boto3 is required for live Bedrock catalog checks") from exc
    try:
        return boto3.client("bedrock", region_name=region_name)
    except ProfileNotFound:
        os.environ.pop("AWS_PROFILE", None)
        return boto3.client("bedrock", region_name=region_name)


def check_model_catalog_availability(
    client: BedrockCatalogLike,
    *,
    expected_model_ids: tuple[str, ...] = EXPECTED_STAGE2_MODEL_IDS,
) -> list[BedrockModelAvailability]:
    """Verify that required model IDs are listed by the Bedrock catalog."""

    summaries = _list_catalog_and_inference_profile_summaries(client)
    by_id = {summary.get("modelId") or summary.get("inferenceProfileId"): summary for summary in summaries}
    results: list[BedrockModelAvailability] = []
    for model_id in dict.fromkeys(expected_model_ids):
        summary = by_id.get(model_id)
        results.append(
            BedrockModelAvailability(
                model_id=model_id,
                listed=summary is not None,
                provider=summary.get("providerName") if summary else None,
                model_name=(summary.get("modelName") or summary.get("inferenceProfileName")) if summary else None,
            )
        )
    return results


def _list_catalog_and_inference_profile_summaries(client: BedrockCatalogLike) -> list[dict[str, Any]]:
    summaries = list(client.list_foundation_models().get("modelSummaries", []))
    list_profiles = getattr(client, "list_inference_profiles", None)
    if callable(list_profiles):
        profiles = list_profiles().get("inferenceProfileSummaries", [])
        summaries.extend({"modelId": item.get("inferenceProfileId"), **item} for item in profiles)
    return summaries


class BedrockEmbeddingModel:
    """Cohere/Titan embedding adapter with the same API as the local embedder."""

    def __init__(
        self,
        *,
        client: BedrockRuntimeLike | None = None,
        model_id: str = DEFAULT_EMBED_MODEL_ID,
        region_name: str = DEFAULT_BEDROCK_REGION,
        input_type: str = "search_document",
        dimension: int = 1024,
    ) -> None:
        self._client = client or make_bedrock_runtime_client(region_name=region_name)
        self.name = resolve_runtime_model_id(model_id)
        self.model_id = resolve_runtime_model_id(model_id)
        self.input_type = input_type
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_query(self, text: str) -> list[float]:
        previous = self.input_type
        self.input_type = "search_query"
        try:
            return self.embed(text)
        finally:
            self.input_type = previous

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if "cohere.embed" in self.model_id:
            body = {
                "texts": texts,
                "input_type": self.input_type,
                "embedding_types": ["float"],
            }
            payload = _invoke_json(self._client, model_id=self.model_id, body=body)
            embeddings = payload.get("embeddings", [])
            if isinstance(embeddings, dict):
                embeddings = embeddings.get("float", [])
            vectors = [_coerce_vector(v) for v in embeddings]
            if vectors and self.dimension != len(vectors[0]):
                self.dimension = len(vectors[0])
            return vectors

        if self.model_id.startswith("amazon.titan-embed-text"):
            return [self._embed_titan(text) for text in texts]

        raise ValueError(f"Unsupported Bedrock embedding model: {self.model_id}")

    def _embed_titan(self, text: str) -> list[float]:
        payload = _invoke_json(
            self._client,
            model_id=self.model_id,
            body={"inputText": text},
        )
        vector = _coerce_vector(payload.get("embedding", []))
        if vector and self.dimension != len(vector):
            self.dimension = len(vector)
        return vector


class BedrockReranker:
    """Cohere Rerank 3.5 adapter that preserves the existing rerank contract."""

    def __init__(
        self,
        *,
        client: BedrockRuntimeLike | None = None,
        model_id: str = DEFAULT_RERANK_MODEL_ID,
        region_name: str = DEFAULT_BEDROCK_REGION,
        top_n: int | None = None,
    ) -> None:
        self._client = client or make_bedrock_runtime_client(region_name=region_name)
        self.model_id = model_id
        self.top_n = top_n

    def __call__(self, query: str, candidates: list[FusionResult]) -> list[FusionResult]:
        return self.rerank(query, candidates)

    def rerank(self, query: str, candidates: list[FusionResult]) -> list[FusionResult]:
        if not candidates:
            return []
        documents = [_document_text(row.chunk) for row in candidates]
        body: dict[str, Any] = {
            "api_version": 2,
            "query": query,
            "documents": documents,
        }
        if self.top_n is not None:
            body["top_n"] = self.top_n
        payload = _invoke_json(self._client, model_id=self.model_id, body=body)
        ordered: list[FusionResult] = []
        seen: set[int] = set()
        for item in payload.get("results", []):
            idx = int(item.get("index", -1))
            if 0 <= idx < len(candidates):
                row = candidates[idx]
                row.rrf_score += float(item.get("relevance_score", 0.0))
                ordered.append(row)
                seen.add(idx)
        for idx, row in enumerate(candidates):
            if idx not in seen:
                ordered.append(row)
        return ordered

    def probe(self) -> bool:
        sample = FusionResult(
            Chunk(
                chunk_id="probe",
                document_id="DOC-PROBE",
                document_name="Probe",
                source_type="probe",
                text="home office deduction probe document",
                article="probe",
                paragraph="1",
            ),
            rrf_score=0.0,
        )
        return bool(self.rerank("home office deduction", [sample]))


def resolve_rerank_model_id(
    *,
    preferred_model_id: str = DEFAULT_RERANK_MODEL_ID,
    inference_profile_id: str = DEFAULT_RERANK_INFERENCE_PROFILE_ID,
) -> str:
    return inference_profile_id or preferred_model_id


class BedrockCitationGenerator:
    """Guarded Claude adapter; falls back to deterministic citation-safe output.

    Stage 2 validates payload shape and live invocation availability. The final
    zero-hallucination guarantee still comes from citation validation after this
    adapter. If a model response cannot be parsed into citation-complete claims,
    the adapter returns the deterministic extractive composer output instead of
    fabricating unsupported citations.
    """

    def __init__(
        self,
        *,
        client: BedrockRuntimeLike | None = None,
        model_id: str = DEFAULT_GENERATION_MODEL_ID,
        region_name: str = DEFAULT_BEDROCK_REGION,
        max_tokens: int = 700,
        temperature: float = 0.0,
    ) -> None:
        self._client = client or make_bedrock_runtime_client(region_name=region_name)
        self.model_id = resolve_runtime_model_id(model_id)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def __call__(self, query: str, authorized_context: list[Chunk]) -> GeneratedAnswer:
        return self.compose(query, authorized_context)

    def compose(self, query: str, authorized_context: list[Chunk], *, max_claims: int = 4) -> GeneratedAnswer:
        deterministic = compose_answer(query, authorized_context, max_claims=max_claims)
        if deterministic.abstained:
            return deterministic

        prompt = build_citation_prompt(query, authorized_context[:max_claims])
        payload = _invoke_json(
            self._client,
            model_id=self.model_id,
            body={
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            },
        )
        parsed = parse_claude_citation_response(payload, authorized_context)
        return parsed or deterministic


def build_citation_prompt(query: str, authorized_context: list[Chunk]) -> str:
    context_lines = []
    for chunk in authorized_context:
        context_lines.append(
            json.dumps(
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "document_name": chunk.document_name,
                    "article": chunk.article,
                    "paragraph": chunk.paragraph,
                    "text": chunk.text,
                },
                ensure_ascii=False,
            )
        )
    return (
        "You answer fiscal/legal questions using only the authorized context. "
        "Every claim must include a citation with chunk_id, document_id, document_name, article, and paragraph. "
        "If the context is insufficient, return JSON with abstained=true.\n\n"
        f"Question: {query}\n\nAuthorized context JSON lines:\n"
        + "\n".join(context_lines)
        + "\n\nReturn strict JSON: {\"answer\": string, \"claims\": "
        "[{\"text\": string, \"chunk_id\": string}], \"abstained\": boolean, \"abstention_reason\": string|null}."
    )


def parse_claude_citation_response(payload: dict[str, Any], authorized_context: list[Chunk]) -> GeneratedAnswer | None:
    text = _extract_claude_text(payload)
    if not text:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if data.get("abstained"):
        return GeneratedAnswer(
            text="",
            citations=[],
            abstained=True,
            abstention_reason=data.get("abstention_reason") or "bedrock_abstained",
        )
    by_id = {chunk.chunk_id: chunk for chunk in authorized_context}
    claims: list[str] = []
    citations: list[Citation] = []
    for claim in data.get("claims", []):
        chunk = by_id.get(claim.get("chunk_id"))
        if chunk is None:
            return None
        citation = Citation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            article=chunk.article,
            paragraph=chunk.paragraph,
        )
        if not citation.is_complete():
            return None
        claims.append(f"{claim.get('text', '').strip()} {citation.format()}")
        citations.append(citation)
    if not claims:
        return None
    return GeneratedAnswer(text="\n".join(claims), citations=citations, abstained=False)


def _invoke_json(
    client: BedrockRuntimeLike,
    *,
    model_id: str,
    body: dict[str, Any],
    max_retries: int = 5,
) -> dict[str, Any]:
    """Invoke a Bedrock model with exponential backoff on ThrottlingException."""
    import time

    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            raw_body = response.get("body", b"{}")
            if hasattr(raw_body, "read"):
                raw_body = raw_body.read()
            if isinstance(raw_body, bytes):
                raw_body = raw_body.decode("utf-8")
            return json.loads(raw_body)
        except Exception as exc:
            exc_name = type(exc).__name__
            # Retry on throttling or transient service errors
            if "ThrottlingException" in exc_name or "ServiceUnavailable" in exc_name or "Throttling" in str(exc):
                last_exc = exc
                if attempt < max_retries - 1:
                    time.sleep(delay)
                    delay = min(delay * 2, 30.0)  # cap at 30 seconds
                    continue
            raise
    raise last_exc  # type: ignore[misc]


def _extract_claude_text(payload: dict[str, Any]) -> str:
    parts = payload.get("content", [])
    texts = [part.get("text", "") for part in parts if part.get("type") == "text"]
    return "\n".join(texts).strip()


def _coerce_vector(value: Any) -> list[float]:
    if isinstance(value, str):
        try:
            decoded = base64.b64decode(value)
            return [float(b) for b in decoded]
        except Exception:
            return []
    return [float(v) for v in value]


def _document_text(chunk: Chunk) -> str:
    return f"{chunk.document_name}\nArticle {chunk.article}, Paragraph {chunk.paragraph}\n{chunk.text}"
