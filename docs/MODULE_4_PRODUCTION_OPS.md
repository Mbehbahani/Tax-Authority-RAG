# Module 4: Production Ops, Security & Evaluation

## Objective

Design production operations, semantic caching, database-level security, CI/CD evaluation, observability, and performance controls for a zero-hallucination tax RAG system.

## Design

### Semantic Caching

- Use Redis for conservative semantic caching of FAQ-style answers only.
- Start with cosine similarity threshold `0.95`; never go below `0.92` for tax/legal answers without formal evaluation.
- Cache only citation-complete, authorization-safe answers.
- Cache key must include normalized query hash, embedding model version, corpus version, role scope, clearance, classification scope, allowed roles hash, and citation ids hash.
- Do not share cached answers across roles if citations or authorization scope differ.
- Invalidate on corpus version change, document version change, embedding model change, citation set change, RBAC policy change, or classification change.

### Database-Level Security

- Enforce RBAC at OpenSearch retrieval level using Document-Level Security and query-time filters.
- Filtering must occur before BM25 scoring, KNN vector scoring, fusion, reranking, prompt construction, LLM generation, cache lookup, and cache write.
- This prevents vector leakage and ranking contamination because unauthorized documents are excluded from the candidate set before scoring.
- The LLM is never an authorization component and never receives unauthorized chunks.

### CI/CD and Evaluation

- Use PR, main, and release gates.
- Evaluate every new embedding model, reranker, prompt, or LLM before production.
- Track Ragas/DeepEval-style metrics: Faithfulness, Context Precision, Context Recall, Answer Relevance, Citation Completeness, Citation Accuracy, RBAC Leakage Count, Abstention Correctness.
- Track performance metrics: TTFT p50/p95/p99, retrieval p95, rerank p95, cache hit rate, OOM events, OpenSearch circuit breakers, latency spikes.
- Log audit events for auth context, filters, retrieved chunk ids, reranked chunk ids, citations, cache decision, grader label, and abstention reason.

## Configs

- Semantic cache threshold: start `0.95`; minimum candidate threshold `0.92` only after evaluation.
- Cache TTL: short default such as `1-24h` for FAQ content; prefer event-based invalidation by corpus version.
- Retrieval timeout: `400-800ms` target budget.
- Rerank timeout: `350ms` p95 target with max `60` candidates.
- TTFT target: `< 1.5s` for optimized/common paths.
- Final context: `5-8` chunks.
- RBAC leakage tolerance: `0`.
- Citation completeness target: `100%`.
- OOM events tolerance: `0`.
- Evaluation gates fixture: [`tests/eval/ci_eval_gates.json`](../tests/eval/ci_eval_gates.json).
- Cache/RBAC security fixture: [`tests/security/cache_rbac_cases.json`](../tests/security/cache_rbac_cases.json).

## Pseudo-code

```python
def answer_question(user, query):
    auth_scope = build_authorization_scope(user)
    cache_key = build_cache_key(
        normalized_query=query,
        role_scope=auth_scope.role_scope,
        clearance=auth_scope.clearance,
        classification_scope=auth_scope.classification_scope,
        corpus_version=current_corpus_version(),
        embedding_model_version=current_embedding_version(),
    )

    cached = semantic_cache_lookup(query, cache_key, threshold=0.95)
    if cached and cache_citations_allowed(cached.citations, auth_scope):
        audit("cache_hit", user=user.id, citations=cached.citations)
        return cached.answer

    auth_filter = build_opensearch_filter(auth_scope)
    chunks = retrieve_with_filter(query, auth_filter)  # filter before BM25/KNN scoring
    answer = crag_generate_or_abstain(user, query, chunks)

    if answer.is_citation_complete and answer.is_cache_safe:
        semantic_cache_write(cache_key, answer)

    audit(
        "rag_answer",
        user=user.id,
        filters=auth_filter,
        retrieved_chunk_ids=[c.id for c in chunks],
        citation_ids=answer.citation_ids,
        abstained=answer.abstained,
    )
    return answer
```

OpenSearch helpdesk filter example:

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

- Semantic cache safety tests in [`tests/security/cache_rbac_cases.json`](../tests/security/cache_rbac_cases.json).
- RBAC/LLM tests in [`tests/security/rbac_llm_scenarios.json`](../tests/security/rbac_llm_scenarios.json).
- Zero-hallucination tests in [`tests/eval/zero_hallucination_scenarios.json`](../tests/eval/zero_hallucination_scenarios.json).
- CI/CD eval gate tests in [`tests/eval/ci_eval_gates.json`](../tests/eval/ci_eval_gates.json).
- Performance tests in [`tests/perf/full_perf.json`](../tests/perf/full_perf.json).
- Test that helpdesk cannot retrieve, rerank, prompt, generate, or cache FIOD content.
- Test that same semantic query with different roles does not share unsafe cache entries.
- Test that new embedding model cannot pass release gate if context precision, faithfulness, or RBAC leakage thresholds fail.
- Test alerting on p95/p99 latency spikes, OOM events, OpenSearch circuit breaker trips, and citation completeness drops.

## Tradeoffs

- Semantic caching reduces TTFT and cost but is risky for tax advice; high thresholds and authorization-scoped keys are mandatory.
- Database-level filtering may reduce recall for lower-privilege users, but this is required for security.
- Strict eval gates slow releases but prevent regressions in faithfulness, citations, and RBAC.
- Rich audit logging increases storage cost but is necessary for legal accountability and incident response.

