# Stage 2 Bedrock Compatibility Report

## 1. Executive Summary

Stage 2 adds AWS Bedrock compatibility without replacing the deterministic local
RAG safety path. The project now has opt-in adapters for:

- Bedrock model catalog and inference-profile availability checks.
- Cohere Embed v4 embeddings through Bedrock Runtime.
- Claude generation through Bedrock Runtime with citation validation fallback.
- Cohere Rerank 3.5 request/response contract support.

The default application and test suite still run offline. Live AWS calls are
only made when `BEDROCK_LIVE_INTEGRATION=true` is explicitly set.

## 2. What Was Added

| File | Purpose |
| --- | --- |
| [`app/rag/bedrock.py`](../app/rag/bedrock.py) | Bedrock catalog/runtime adapters for embeddings, generation, reranking, and model availability checks. |
| [`tests/unit/test_bedrock_adapters.py`](../tests/unit/test_bedrock_adapters.py) | Offline tests with fake Bedrock clients for payload shape, parser safety, catalog/inference-profile handling, and deterministic fallback. |
| [`tests/integration/test_bedrock_live_optional.py`](../tests/integration/test_bedrock_live_optional.py) | Optional live Bedrock tests, skipped unless `BEDROCK_LIVE_INTEGRATION=true`. |
| [`requirements.txt`](../requirements.txt) | Adds `boto3` for Bedrock control-plane/runtime clients. |
| [`.env.example`](../.env.example) | Updated runtime model IDs to active EU inference profiles where required. |

## 3. Model and Account Checks

AWS identity check succeeded:

```text
Account: 780822965578
Arn: arn:aws:iam::780822965578:user/mohabehb
```

Bedrock model catalog in `eu-central-1` lists the original target base models:

```text
cohere.embed-v4:0                         Cohere     Embed v4
amazon.titan-embed-text-v2:0              Amazon     Titan Embeddings G2 - Text
anthropic.claude-3-haiku-20240307-v1:0    Anthropic  Claude 3 Haiku
anthropic.claude-3-7-sonnet-20250219-v1:0 Anthropic  Claude 3.7 Sonnet
cohere.rerank-v3-5:0                      Cohere     Rerank 3.5
```

Runtime invocation showed an important Bedrock distinction:

- `cohere.embed-v4:0` is listed but does **not** support on-demand invocation in
  this account/region. Bedrock requires an inference profile.
- `anthropic.claude-3-haiku-20240307-v1:0` is listed but is marked legacy for
  this account because it has not been actively used recently.
- `eu.cohere.embed-v4:0` works for live embedding invocation.
- `eu.anthropic.claude-haiku-4-5-20251001-v1:0` works for live Claude fast-model
  invocation.

Therefore [`.env.example`](../.env.example) now uses active EU runtime IDs:

```text
BEDROCK_GENERATION_MODEL_ID=eu.anthropic.claude-3-7-sonnet-20250219-v1:0
BEDROCK_FAST_MODEL_ID=eu.anthropic.claude-haiku-4-5-20251001-v1:0
BEDROCK_JUDGE_MODEL_ID=eu.anthropic.claude-3-7-sonnet-20250219-v1:0
BEDROCK_EMBEDDING_MODEL_ID=eu.cohere.embed-v4:0
BEDROCK_FALLBACK_EMBEDDING_MODEL_ID=amazon.titan-embed-text-v2:0
BEDROCK_RERANK_MODEL_ID=cohere.rerank-v3-5:0
```

## 4. Validation Results

Default offline test suite:

```text
83 passed, 6 skipped in 1.12s
```

Optional live Bedrock tests:

```text
3 passed, 4 warnings in 2.80s
```

The warnings are from `botocore` using `datetime.utcnow()` internally and do not
indicate a project failure.

## 5. How to Run Stage 2 Checks

Offline default suite:

```text
python -m pytest -q
```

Live AWS/Bedrock suite:

```text
set BEDROCK_LIVE_INTEGRATION=true&& python -m pytest tests/integration/test_bedrock_live_optional.py -q
```

Manual catalog checks:

```text
aws sts get-caller-identity --output json
aws bedrock list-foundation-models --region eu-central-1 --output table
aws bedrock list-inference-profiles --region eu-central-1 --output table
```

## 6. Safety Boundary

Stage 2 does **not** make the production answer path depend blindly on Bedrock
generation. [`BedrockCitationGenerator`](../app/rag/bedrock.py) requires parsed
claims to cite chunk IDs from the authorized context. If the model returns bad
JSON, missing citations, or a citation outside authorized retrieved chunks, the
adapter falls back to the deterministic extractive composer rather than
fabricating unsupported claims.

The zero-hallucination and RBAC invariants remain enforced by the existing graph
validation stage and tests.

## 7. Remaining Gaps / Next Stage

1. Wire `BedrockEmbeddingModel` into ingestion/retrieval behind an explicit
   environment flag and re-index OpenSearch with real 1024-dimensional Cohere
   embeddings.
2. Wire `BedrockReranker` into the retrieval pipeline behind a feature flag and
   compare ranking quality against the deterministic reranker.
3. Wire `BedrockCitationGenerator` into the graph behind a feature flag, then
   execute DeepEval scenarios against Sonnet/Haiku routing.
4. Confirm whether `cohere.rerank-v3-5:0` needs an inference profile or can be
   invoked directly in this account before enabling live rerank calls.
5. Keep the default CI path offline unless AWS credentials and model invocation
   budget are explicitly configured.
