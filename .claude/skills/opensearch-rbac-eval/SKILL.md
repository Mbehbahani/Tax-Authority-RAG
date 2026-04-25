---
name: opensearch-rbac-eval
description: Guidance for OpenSearch hybrid retrieval, HNSW configuration, RBAC-before-retrieval, reranking, and retrieval/evaluation metrics.
---

# Skill: OpenSearch RBAC Evaluation

Use this skill when designing retrieval, OpenSearch configuration, RBAC filters, and metrics.

## Guidance

- Use hybrid retrieval: lexical BM25 plus vector search.
- Use HNSW starting defaults: `m=32`, `ef_construction=256`, `ef_search=128`.
- Start with lexical `top_k=50`, vector `top_k=50`, fused candidates `60-80`, rerank top `60`, final context `5-8`.
- Use Reciprocal Rank Fusion as default fusion.
- Apply RBAC and classification filters before retrieval.
- Consider document-level security and filtered aliases where supported.
- Track metrics: recall@k, precision@k, MRR, nDCG, citation accuracy, RBAC leakage, p50/p95/p99 latency, TTFT, cache hit rate.

## Stage 1 Implementation Best Practices

- Implement an OpenSearch-compatible retrieval adapter from the start.
- Prefer local OpenSearch in Docker Compose when feasible; keep a mock fallback only for local machine limitations.
- Keep mapping/query contracts in tests even when using the mock fallback.
- RBAC filters must be applied before BM25, KNN/vector scoring, fusion, reranking, and prompt construction.
- Do not rely on post-filtering after retrieval as the main security control.
- Use keyword fields for exact identifiers such as `ecli`, `document_id`, `article`, and classification metadata.
- Keep vector dimensions configurable because Cohere/Titan embedding dimensions may differ.
- Keep top-k, HNSW, and rerank caps configurable through environment/config files.
- Validate that restricted documents are absent from BM25 results, vector results, fused candidates, rerank input, prompt context, and cache entries.

