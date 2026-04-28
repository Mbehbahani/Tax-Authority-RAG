# Stage 4 DeepEval and Retrieval Quality Report

## 1. Executive Summary

Stage 4 turns the previous connectivity and wiring work into formal evaluation
infrastructure. The project now has DeepEval installed, deterministic offline
evaluation metrics over the zero-hallucination and RBAC scenarios, live Cohere
Embed v4 retrieval-quality checks, live Cohere Rerank 3.5 runtime probing, and
assessment-ready metric tables.

The default suite remains deterministic and safe. Live AWS/Bedrock checks are
still opt-in through explicit environment flags.

## 2. What Was Added

| File | Purpose |
| --- | --- |
| [`app/rag/evaluation.py`](../app/rag/evaluation.py) | Stage 4 evaluation runner, deterministic metrics, DeepEval availability check, routing-mode summaries, reranker comparison, retrieval-quality comparison, and final assessment table builder. |
| [`tests/eval/test_stage4_formal_evaluation.py`](../tests/eval/test_stage4_formal_evaluation.py) | Offline tests for formal metrics, zero-hallucination scenarios, RBAC scenarios, assessment table generation, reranker comparison, retrieval-quality comparison, and routing-mode summaries. |
| [`tests/integration/test_stage4_live_rerank_embed_optional.py`](../tests/integration/test_stage4_live_rerank_embed_optional.py) | Optional live Bedrock checks for Cohere Embed v4 retrieval quality and Cohere Rerank 3.5 runtime probing. |
| [`app/rag/bedrock.py`](../app/rag/bedrock.py) | Runtime model-ID resolution, ProfileNotFound fallback to default AWS credential chain, Cohere Rerank `api_version` payload fix, and reranker probe. |
| [`requirements.txt`](../requirements.txt) | Adds `deepeval` for the formal evaluation framework. |
| [`.env.example`](../.env.example) | Adds `BEDROCK_RERANK_INFERENCE_PROFILE_ID` for accounts/regions that require a rerank inference profile. |

## 3. Evaluation Metrics Covered

The Stage 4 evaluator produces the final assessment metrics requested for the
architecture narrative:

| Metric | Source |
| --- | --- |
| Faithfulness | Deterministic citation-membership proxy; DeepEval-ready wrapper. |
| Answer relevance | Scenario expected-behavior alignment. |
| Citation completeness | Every citation has chunk ID, document ID, document name, article, and paragraph. |
| Citation accuracy | Every citation chunk ID is a member of the authorized retrieved context. |
| Abstention correctness | Scenarios that require abstention/clarification must abstain. |
| RBAC leakage count | Forbidden/restricted document citations count. |
| Prompt-injection success count | Prompt-injection scenario must abstain/no leak. |
| TTFT p95 | Local elapsed-time proxy captured per scenario. |
| Estimated cost | Transparent rough per-mode token-cost estimate for comparison. |

## 4. Validation Results

Default offline suite:

```text
97 passed, 9 skipped in 1.16s
```

Live Bedrock compatibility suite:

```text
3 passed, 4 warnings in 3.10s
```

Live Stage 4 retrieval/rerank suite:

```text
2 passed, 2 warnings in 1.45s
```

The warnings are from `pytest-asyncio` configuration and `botocore` internal
`datetime.utcnow()` usage. They do not indicate failed project checks.

## 5. Cohere Rerank 3.5 Runtime Confirmation

The live Stage 4 rerank probe initially revealed the correct Bedrock payload
requirements:

- `api_version` is required.
- `return_documents` is not permitted for the Bedrock Cohere Rerank payload.

[`BedrockReranker`](../app/rag/bedrock.py) now sends:

```json
{
  "api_version": 2,
  "query": "...",
  "documents": ["..."]
}
```

The live rerank probe now passes with `cohere.rerank-v3-5:0` in `eu-central-1`.
No inference-profile override was required in this account at the time of the
test. If another account/region requires one, set `BEDROCK_RERANK_INFERENCE_PROFILE_ID`.

## 6. Cohere Embed v4 Retrieval Quality Check

Stage 4 added an optional live retrieval-quality comparison using
`eu.cohere.embed-v4:0`. The test builds a real Cohere-embedding-backed local
retrieval backend and compares it with the deterministic baseline for overlap
and citation completeness.

Result: live Cohere Embed v4 retrieval returned citation-complete context and
passed the retrieval-quality smoke check.

## 7. Haiku vs Sonnet Routing Evaluation

[`app/rag/model_routing.py`](../app/rag/model_routing.py) remains conservative:

- Haiku is eligible only for low-risk helpdesk/documentation tasks if all
  evaluation thresholds pass.
- Sonnet/high-risk route is required for legal interpretation, ECLI/case-law,
  fraud/FIOD, exact numeric/percentage/deduction-limit questions, version/date
  ambiguity, and legal-counsel/FIOD roles.
- Unknown route requests fall back to deterministic mode.

Stage 4 added summary generation over routing modes so deterministic, Haiku,
and Sonnet-style paths can be compared over the same scenario suite.

## 8. How to Run

Default offline validation:

```text
python -m pytest -q
```

Live Bedrock compatibility checks:

```text
set BEDROCK_LIVE_INTEGRATION=true&& python -m pytest tests/integration/test_bedrock_live_optional.py -q
```

Live Cohere Embed v4 + Cohere Rerank checks:

```text
set STAGE4_LIVE_RETRIEVAL_EVAL=true&& python -m pytest tests/integration/test_stage4_live_rerank_embed_optional.py -q
```

## 9. Final Assessment-Ready Evaluation Table

The implementation now produces the following table shape through
[`build_assessment_table()`](../app/rag/evaluation.py):

| Metric | Target |
| --- | --- |
| faithfulness | >= 0.98 |
| answer_relevance | >= 0.90 |
| citation_completeness | 1.0 |
| citation_accuracy | 1.0 |
| abstention_correctness | >= 0.98 |
| rbac_leakage_count | 0 |
| prompt_injection_success_count | 0 |
| ttft_p95_seconds | < 1.5 |
| estimated_cost_per_1000_queries | track |

This table is ready to be used in the final assessment narrative and can be
populated from deterministic, Haiku, and Sonnet-mode summaries.

## 10. Remaining Work Before Final Answer

1. Run a broader live Haiku-vs-Sonnet scenario evaluation if cost/time permits.
2. Optionally re-index the real Docker OpenSearch backend with full Cohere
   Embed v4 vectors instead of the in-memory retrieval-quality smoke path.
3. Convert the deterministic evaluator into full DeepEval judge calls if a
   judge-model budget is approved.
4. Move to Stage 5: write the final assessment answer using the proven reports,
   architecture, metrics, routing policy, and production-readiness discussion.
