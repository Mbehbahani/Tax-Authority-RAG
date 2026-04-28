# Stage 3 Bedrock-Powered RAG Evaluation and Model-Routing Report

## 1. Executive Summary

Stage 3 adds controlled Bedrock-powered RAG evaluation and conservative
model-routing validation. The default system remains deterministic/offline, but
the RAG graph can now opt into Bedrock embeddings, Bedrock reranking, and
Bedrock generation through explicit feature flags.

The key safety decision is unchanged: every generated answer still passes
mandatory citation validation, and every citation must refer to chunks in the
authorized retrieved context. If a Bedrock generation response cannot be parsed
or cites a chunk outside the authorized context, the system falls back to the
deterministic extractive composer rather than trusting model memory.

## 2. What Was Added

| File | Purpose |
| --- | --- |
| [`app/rag/graph.py`](../app/rag/graph.py) | `GraphDeps` now accepts optional reranker and answer-composer hooks for Bedrock-backed evaluation. |
| [`app/rag/retrieval.py`](../app/rag/retrieval.py) | `hybrid_retrieve` now accepts an optional reranker while preserving deterministic default reranking. |
| [`app/rag/service.py`](../app/rag/service.py) | `build_service_from_paths` now wires optional Bedrock embeddings, reranking, and generation from environment flags. |
| [`app/rag/model_routing.py`](../app/rag/model_routing.py) | Conservative router for deterministic, Haiku-fast, and Sonnet/high-risk modes plus evaluation metrics helpers. |
| [`tests/unit/test_stage3_model_routing.py`](../tests/unit/test_stage3_model_routing.py) | Offline tests for routing, injected composer wiring, service feature-flag defaults, and evaluation metrics. |
| [`tests/integration/test_stage3_bedrock_rag_optional.py`](../tests/integration/test_stage3_bedrock_rag_optional.py) | Optional live Bedrock RAG graph test for authorized citation-preserving generation. |
| [`.env.example`](../.env.example) | Adds Stage 3 feature flags: `BEDROCK_EMBEDDINGS_ENABLED`, `BEDROCK_RERANK_ENABLED`, `BEDROCK_GENERATION_ENABLED`, and `MODEL_ROUTING_MODE`. |

## 3. Feature Flags

All Stage 3 Bedrock-powered behavior is off by default:

```text
BEDROCK_EMBEDDINGS_ENABLED=false
BEDROCK_RERANK_ENABLED=false
BEDROCK_GENERATION_ENABLED=false
MODEL_ROUTING_MODE=deterministic
```

Recommended safe progression:

1. Enable only generation first for evaluation:
   `BEDROCK_GENERATION_ENABLED=true`.
2. Enable reranking separately after confirming the Cohere Rerank runtime ID or
   inference-profile behavior.
3. Enable Bedrock embeddings only when ready to re-index OpenSearch with the
   real embedding dimension.

## 4. Model-Routing Rule

[`ModelRouter`](../app/rag/model_routing.py) applies a conservative policy:

- `deterministic`: default offline safety baseline.
- `haiku`: allowed only for low-risk helpdesk/documentation-style questions.
- `sonnet`: selected for high-risk legal interpretation, ECLI/case law, fraud,
  FIOD, exact numeric/percentage/deduction-limit questions, version/effective
  date questions, and legal-counsel/FIOD roles.

If Haiku is requested for a high-risk query, routing escalates to Sonnet.

## 5. Validation Results

Default offline validation:

```text
90 passed, 7 skipped in 1.04s
```

Live Bedrock compatibility validation:

```text
3 passed, 4 warnings in 3.89s
```

Live Stage 3 Bedrock RAG graph validation:

```text
1 passed, 1 warning in 2.13s
```

The warnings are `botocore` internal `datetime.utcnow()` deprecation warnings
and do not indicate a failed project check.

## 6. How to Run

Default offline suite:

```text
python -m pytest -q
```

Live Bedrock compatibility suite:

```text
set BEDROCK_LIVE_INTEGRATION=true&& python -m pytest tests/integration/test_bedrock_live_optional.py -q
```

Live Bedrock-backed RAG graph suite:

```text
set STAGE3_LIVE_BEDROCK_RAG=true&& python -m pytest tests/integration/test_stage3_bedrock_rag_optional.py -q
```

## 7. Current Status Against Stage 3 Goals

| Goal | Status | Notes |
| --- | --- | --- |
| Optional Bedrock generation through RAG graph | Met | Live Bedrock generation test passes and citations remain authorized. |
| Optional Bedrock reranker hook | Met | Hook is wired and offline-tested; live Cohere Rerank invocation still needs a runtime-ID check. |
| Optional Bedrock embeddings hook | Met | Hook is wired; real embedding use should be paired with OpenSearch re-indexing. |
| Conservative model routing | Met | Haiku is restricted to low-risk; high-risk escalates to Sonnet. |
| Offline evaluation metrics helper | Met | Citation completeness, citation accuracy, RBAC leakage, abstention, and latency are captured. |
| DeepEval execution | Not yet | Fixtures and metrics are ready, but the `deepeval` dependency and judge runs are still a next step. |

## 8. Remaining Gaps / Next Stage

1. Add `deepeval` and implement formal DeepEval tests over the existing
   zero-hallucination and RBAC scenarios.
2. Confirm the correct Bedrock runtime/inference-profile ID for Cohere Rerank
   3.5, then run live reranker comparisons.
3. Re-index OpenSearch with real Cohere Embed v4 vectors and compare retrieval
   quality against deterministic embeddings.
4. Run Haiku-vs-Sonnet evaluation on the scenario suite and apply the routing
   rule from [`tests/eval/model_routing_eval_plan.json`](../tests/eval/model_routing_eval_plan.json).
5. Produce a final assessment-ready evaluation table with faithfulness,
   citation completeness, citation accuracy, abstention correctness, RBAC
   leakage count, TTFT p95, and cost estimates.
