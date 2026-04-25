# Command: Write Final Technical Assessment

Produce the final answer for the Enterprise RAG Architecture for the Tax Authority. If the assessment prompt asks for the OpenSearch-primary format, structure the answer exactly as the seven modules below. Otherwise, map the content back into the original four assessment modules.

## OpenSearch-Primary Required Module Structure

1. Module 1 — Index Design & Ingestion
2. Module 2 — Strict RBAC Implementation
3. Module 3 — Hybrid Retrieval
4. Module 4 — Reranking Strategy
5. Module 5 — Failure Handling / Self-Healing
6. Module 6 — Semantic Caching
7. Module 7 — Testing & Validation

## Original Assessment Module Mapping

1. Ingestion & Knowledge Structuring
2. Retrieval Strategy
3. Agentic RAG & Self-Healing
4. Production Ops, Security & Evaluation

## Include in the OpenSearch-Primary Answer

- Text architecture diagram.
- Metadata schema for documents and chunks.
- Full OpenSearch index mapping with `knn_vector`, HNSW, metadata fields, role fields, classification fields, and citation fields.
- HNSW defaults: `m=32`, `ef_construction=256`, runtime `ef_search=128` starting point.
- Memory optimization strategy: quantization, shard sizing, replica strategy, force merge/read replicas where appropriate, bounded candidates.
- Example ingestion document JSON.
- Strict RBAC using Document-Level Security and query-time filters.
- Exact OpenSearch query filters for `user_role = "helpdesk"` and `user_clearance = 2`.
- Explain why retrieval-level filtering prevents vector leakage, ranking contamination, and LLM inference attacks.
- Full hybrid OpenSearch query JSON using BM25 and KNN vector search.
- Hybrid fusion with Reciprocal Rank Fusion by default, or weighted scoring if justified.
- Top-k values: initial retrieval around 100 candidates and final reranked around 10, with rationale.
- Explain why hybrid retrieval is necessary for exact identifiers such as ECLI and semantic tax/legal reasoning.
- Cross-encoder reranking strategy with retrieve -> rerank -> select top-N pipeline.
- Reranking latency controls and max candidates for reranking.
- LangGraph CRAG state machine.
- Retrieval grader with relevant / ambiguous / irrelevant outcomes.
- Self-healing actions: irrelevant -> expand query or HyDE; ambiguous -> query decomposition; relevant -> generation.
- Redis semantic cache threshold and authorization-safe cache key design.
- Cache invalidation strategy and lookup flow.
- RBAC-before-retrieval logic.
- CI/CD and observability plan.
- Automated tests for retrieval quality, hallucination/faithfulness, RBAC security, and performance.
- Retrieval metrics: Context Precision, Recall@K, MRR.
- RAGAS or DeepEval metrics: Faithfulness and Answer Relevance.
- RBAC tests: forbidden document negative test, leakage test, cross-role test, adversarial indirect request test.
- Performance tests simulating 20M+ chunks and concurrent queries.
- Tests for TTFT < 1.5s, p50/p95/p99 latency, OOM risk, memory pressure, and latency spikes.
- Clear conclusion.

## Hard Constraints

- Do not suggest post-filtering after retrieval.
- Do not allow the LLM to decide authorization.
- Do not leave OpenSearch, RBAC, testing, or performance details abstract.
- Everything security-critical must be enforceable at the system or retrieval layer.

Keep deployment secondary. Mention AWS light infrastructure only as optional future implementation support.

