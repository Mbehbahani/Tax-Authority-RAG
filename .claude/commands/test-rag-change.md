# Command: Test a RAG Architecture or Code Change

For any proposed change, produce a test plan with:

1. Impacted layers: ingestion, retrieval, graph, security, cache, API, evaluation, CI/CD.
2. Unit tests.
3. Integration tests.
4. Security tests, including RBAC leakage and FIOD exclusion for helpdesk.
5. RAG evaluation tests, including citation completeness and groundedness.
6. Performance tests for TTFT below 1.5s, p95/p99 latency, OOM risk, memory pressure, and latency spikes.
7. PR, main, and release gates.

## LLM-Specific Authorization Tests

- Verify prompt construction receives only authorized chunks after OpenSearch DLS/query-time filtering.
- Verify restricted chunks are absent before reranking, not merely removed after ranking.
- Verify generated citations are a subset of authorized retrieved citation ids.
- Verify prompt injection cannot change role, clearance, classification, or DLS filters.
- Verify cache reuse is denied across different role/clearance/classification scopes.

## Zero-Hallucination Tests

- Verify every generated claim has document name, article, and paragraph.
- Verify every citation is present in the authorized retrieved context.
- Verify the cited passage directly supports the claim.
- Verify numeric fiscal advice exactly matches cited text.
- Verify missing, conflicting, outdated, or unauthorized evidence causes abstention.
- Use [`tests/eval/zero_hallucination_scenarios.json`](../../tests/eval/zero_hallucination_scenarios.json) as the prepared fixture.

Do not accept changes that weaken authorization, citations, or abstention behavior.

