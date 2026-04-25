# Test Strategy

## Correctness Tests

- Chunking preserves legal hierarchy.
- Metadata includes document name, article, paragraph, version, classification, and allowed roles.
- Citation formatter rejects incomplete citations.

## Retrieval Tests

- Recall@k, precision@k, MRR, and nDCG on curated queries.
- Hybrid retrieval and RRF ranking tests.
- Reranker cap and final context size tests.

## Security Tests

- RBAC filters are applied before retrieval.
- Helpdesk users cannot retrieve FIOD/fraud-investigation documents.
- Cache keys are authorization-scoped.
- Prompt-injection attempts cannot override security policy.
- LLM prompt construction includes only authorized chunks.
- The LLM never receives unauthorized chunk text, metadata, citation ids, or reranker candidates.
- Every generated citation must be a member of the authorized retrieved context set.
- Same semantic query with different roles must produce role-appropriate retrieved context and different cache keys.

## Role and Access Test Matrix

| Test Role | Clearance | Expected Access | Expected Denial |
| --- | --- | --- | --- |
| `helpdesk` | `2` | FAQ, e-learning, non-sensitive policy | FIOD/fraud documents, legal privileged memos |
| `tax_inspector` | `3` | legislation, case law, operational manuals | FIOD unless explicitly granted |
| `legal_counsel` | `4` | legislation, case law, legal memos | FIOD unless explicitly granted |
| `fiod_investigator` | `5` | assigned FIOD case material | unassigned case material |

Prepared acceptance scenarios are defined in [`docs/RBAC_LLM_TEST_SCENARIOS.md`](RBAC_LLM_TEST_SCENARIOS.md) and machine-readable fixtures are in [`tests/security/rbac_llm_scenarios.json`](../tests/security/rbac_llm_scenarios.json).

## LLM Authorization Tests

- Prompt context test: assert unauthorized chunk ids are absent from the LLM prompt.
- Abstention test: if all relevant documents are unauthorized, response must be an abstention with no restricted details.
- Prompt injection test: attempts to override role, clearance, or classification filters must fail.
- Citation membership test: generated citations must be subset of retrieved authorized citations.
- Cache isolation test: answers are cached by role scope, clearance scope, corpus version, and citation ids.

## Citation Tests

- Every claim has document name, article, and paragraph.
- Answers abstain when citations are unavailable.
- Every generated claim is atomic and mapped to an authorized retrieved chunk.
- The cited passage must directly support the claim.
- Numeric fiscal values must match the cited passage exactly.
- Effective-date/version conflicts must trigger abstention unless resolved by retrieved context.
- Fabricated document names, articles, paragraphs, or citations fail the test.

Prepared zero-hallucination scenarios are defined in [`docs/ZERO_HALLUCINATION_TEST_SCENARIOS.md`](ZERO_HALLUCINATION_TEST_SCENARIOS.md) and machine-readable fixtures are in [`tests/eval/zero_hallucination_scenarios.json`](../tests/eval/zero_hallucination_scenarios.json).

## RAG Eval Metrics

- Groundedness, faithfulness, answer relevance, context precision, context recall, citation accuracy, and abstention correctness.

## Performance Tests

- TTFT below 1.5s for smoke paths.
- p95/p99 latency for retrieval, reranking, graph, and generation.
- OOM and memory pressure tests with bounded candidate sets.
- Burst tests for latency spikes and queue behavior.
- Exact identifier query latency, semantic query latency, RBAC-denied query latency, cache-hit TTFT, mixed concurrent workload, and injected latency spike resilience.

Prepared performance scenarios are defined in [`docs/PERFORMANCE_TEST_SCENARIOS.md`](PERFORMANCE_TEST_SCENARIOS.md), [`tests/perf/smoke_queries.json`](../tests/perf/smoke_queries.json), and [`tests/perf/full_perf.json`](../tests/perf/full_perf.json).

## CI/CD Gates

- PR: lint, unit, security smoke, small eval.
- Main: integration, RBAC leakage, retrieval smoke, perf smoke.
- Release: full eval, p95/p99, OOM, load, and audit review.

