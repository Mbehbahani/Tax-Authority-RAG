# Performance and Scale Test Scenarios

Use these scenarios to validate the high-performance requirement: tens of millions of vector chunks with Time-to-First-Token below 1.5 seconds where the architecture claims it is achievable.

## Performance Targets

| Metric | Target | Notes |
| --- | --- | --- |
| TTFT | `< 1.5s` | Measured from API request accepted to first streamed token. |
| Retrieval latency p95 | `< 400ms` | Includes RBAC-filtered BM25/vector retrieval and fusion. |
| Rerank latency p95 | `< 350ms` | Bounded candidate set only. |
| Prompt assembly p95 | `< 100ms` | Includes citation validation and prompt construction. |
| End-to-end p95 | `< 3.5s` | Depends on LLM provider; TTFT is stricter. |
| Error rate | `< 1%` | Under smoke concurrency. |
| OOM events | `0` | Under configured candidate and memory limits. |

## Scale Assumptions

- Corpus: 500,000 documents.
- Chunk count: 20M+ chunks.
- Embedding dimension: document-dependent, commonly 768 or 1024.
- OpenSearch retrieval: HNSW with bounded `ef_search`, RBAC filters applied before retrieval.
- Reranking: maximum 60 candidates by default.
- Final context: 5-8 chunks.

## Scenario 1 — Exact Identifier Query

- Query: `Ruling ECLI:NL:HR:2023:123`
- Expected path: BM25 exact match dominates, vector search optional/supporting.
- TTFT target: `< 1.5s`.
- Expected retrieval p95: `< 250ms`.
- Fail if: exact identifier requires broad semantic scan or exceeds latency target.

## Scenario 2 — Semantic Tax Query

- Query: `deductibility of home office expenses`
- Expected path: hybrid BM25 + vector, RRF, cross-encoder rerank.
- Initial candidates: lexical `50`, vector `50`, fused `60-80`, rerank max `60`, final `5-8`.
- TTFT target: `< 1.5s` for warm service and bounded LLM streaming start.
- Fail if: unbounded reranking or context assembly causes TTFT spike.

## Scenario 3 — RBAC-Filtered Large Corpus Query

- Query: `fraud investigation indicators for home office deductions`
- User: `helpdesk`.
- Expected path: DLS/query-time filters eliminate restricted FIOD content before scoring.
- TTFT target: `< 1.5s` with abstention or safe allowed-context response.
- Fail if: restricted candidates are scored/reranked or latency increases due to post-filtering.

## Scenario 4 — Concurrent Mixed Workload

- Workload: 70% semantic FAQ, 20% exact identifiers, 10% adversarial/RBAC-denied.
- Concurrent users: start with `50`, then `100`, then `250` for release-grade testing.
- Measure: TTFT p50/p95/p99, retrieval p95, rerank p95, error rate, queue time.
- Fail if: p95 TTFT exceeds target for smoke load or p99 shows uncontrolled spikes.

## Scenario 5 — OOM and Memory Pressure

- Simulate: large index, high concurrent KNN, high `ef_search`, rerank candidate bursts.
- Controls expected: bounded `ef_search`, bounded top-k, circuit breakers, memory alarms, request timeouts.
- Fail if: OOM occurs, OpenSearch circuit breaker trips repeatedly, or process memory grows without recovery.

## Scenario 6 — Cache Hit TTFT

- Query: common FAQ such as `What is the Box 1 tax rate for 2024?`
- Expected path: authorization-safe semantic cache hit.
- TTFT target: `< 500ms`.
- Fail if: cache key ignores role, clearance, corpus version, or citation set.

## Scenario 7 — Latency Spike Resilience

- Inject: slow LLM response, slow OpenSearch shard, Redis timeout, reranker slowdown.
- Expected behavior: timeout, degrade safely, abstain if needed, preserve RBAC and citation rules.
- Fail if: system leaks data, drops citations, or retries unboundedly.

## Required Measurements

- API request start time.
- Auth/RBAC filter construction time.
- OpenSearch BM25 latency.
- OpenSearch KNN latency.
- Fusion latency.
- Rerank latency.
- Retrieval grader latency.
- Prompt assembly latency.
- Time to first streamed token.
- End-to-end latency.
- Memory usage and circuit breaker events.
- Cache hit/miss and cache safety decision.

