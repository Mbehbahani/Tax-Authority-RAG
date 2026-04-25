# Module 2: Retrieval Strategy

## Objective

Design high-precision retrieval for mixed exact and semantic legal queries at 20M+ chunk scale, while enforcing RBAC before BM25, vector scoring, fusion, reranking, prompt construction, and generation.

## Design

- Use OpenSearch as the primary retrieval engine.
- Run hybrid retrieval: BM25 for exact identifiers/legal terms and KNN vector search for semantic concepts.
- Apply DLS/query-time RBAC filters before both lexical and vector retrieval.
- Fuse sparse and dense results with Reciprocal Rank Fusion by default.
- Rerank fused candidates with a cross-encoder or enterprise reranking API.
- Return final chunks only if they include complete citation metadata: document name, article/section, paragraph.

Why hybrid is necessary:

- Exact legal identifiers such as `ECLI:NL:HR:2023:123`, article numbers, and document ids are best handled by BM25/keyword fields.
- Semantic concepts such as `deductibility of home office expenses` require dense retrieval.
- RRF avoids brittle score normalization between BM25 and vector scores and performs well when one signal is exact and the other is semantic.

## Configs

- Lexical top-k: `50`.
- Vector top-k: `50`.
- Fused candidates: `60-80`.
- RRF rank constant: `60` starting point.
- Rerank max candidates: `60`.
- Final context chunks: `5-8`.
- HNSW runtime `ef_search`: `128` starting point.
- Exact identifier boosts: `ecli^12`, `document_id^8`, `article^5`, `text^2`.
- Reranker: cross-encoder trained/evaluated on legal retrieval pairs, or enterprise rerank API such as Cohere Rerank if approved.
- Reranker latency budget: p95 `< 350ms` for max `60` candidates.
- Retrieval query fixtures: [`tests/integration/retrieval_query_examples.json`](../tests/integration/retrieval_query_examples.json).
- RRF/rerank fixtures: [`tests/unit/rrf_rerank_cases.json`](../tests/unit/rrf_rerank_cases.json).

## Pseudo-code

```python
def retrieve(query, user, query_embedding):
    auth_filter = build_auth_filter(
        role=user.role,
        clearance=user.clearance,
        need_to_know=user.need_to_know_groups,
    )

    bm25_hits = opensearch.search(
        index="tax-rag-chunks-v1",
        size=50,
        query={
            "bool": {
                "filter": auth_filter,
                "must": [{
                    "multi_match": {
                        "query": query,
                        "fields": ["ecli^12", "document_id^8", "article^5", "text^2"]
                    }
                }]
            }
        },
    )

    vector_hits = opensearch.search(
        index="tax-rag-chunks-v1",
        size=50,
        query={
            "bool": {
                "filter": auth_filter,
                "must": [{
                    "knn": {
                        "embedding": {
                            "vector": query_embedding,
                            "k": 50,
                            "method_parameters": {"ef_search": 128}
                        }
                    }
                }]
            }
        },
    )

    fused = reciprocal_rank_fusion([bm25_hits, vector_hits], rank_constant=60)
    candidates = take(fused, 60)
    assert all(is_authorized(hit, user) for hit in candidates)

    reranked = cross_encoder_rerank(query, candidates)
    final_context = take_with_complete_citations(reranked, 8)
    return final_context
```

Example authorization filter for helpdesk with clearance `2`:

```json
{
  "bool": {
    "filter": [
      {"term": {"allowed_roles": "helpdesk"}},
      {"range": {"classification_level": {"lte": 2}}}
    ],
    "must_not": [
      {"term": {"classification_tags": "FIOD"}},
      {"term": {"classification_tags": "fraud_investigation"}}
    ]
  }
}
```

## Tests

- Exact ECLI query retrieves the case-law document for inspector/legal roles.
- Semantic home-office query retrieves legislation/policy/e-learning for helpdesk but not restricted case law or FIOD material.
- Helpdesk FIOD query returns no restricted documents before fusion and reranking.
- RRF unit tests validate fusion order and stable rank behavior.
- Reranker cap test ensures at most `60` candidates are reranked and at most `8` chunks reach generation.
- Latency tests validate retrieval p95 and rerank p95 targets from [`docs/PERFORMANCE_TEST_SCENARIOS.md`](PERFORMANCE_TEST_SCENARIOS.md).
- Citation test verifies final context chunks all include document name, article/section, and paragraph.

## Tradeoffs

- RRF is safer than raw weighted score fusion because BM25 and vector scores are not naturally comparable.
- Weighted alpha fusion can be used later if calibrated, but legal exact-match queries make RRF a better default.
- Cross-encoder reranking improves precision but must be capped to avoid TTFT spikes.
- Larger top-k improves recall but increases memory, latency, and reranker cost.
- Exact identifiers should be strongly boosted to avoid semantic retrieval burying known legal references.
- RBAC filtering before retrieval prevents ranking contamination and vector leakage; post-filtering is not acceptable.

