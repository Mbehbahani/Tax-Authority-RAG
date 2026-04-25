---
name: rag-test-strategy
description: Guidance for unit, integration, security, RAG evaluation, RBAC leakage, citation, performance, and release-gate tests.
---

# Skill: RAG Test Strategy

Use this skill when designing quality, security, and performance validation.

## Guidance

- Unit tests: chunkers, metadata extraction, filters, citation formatter, graph transitions.
- Integration tests: ingestion to retrieval, API to graph, cache behavior, OpenSearch query generation.
- RAG eval tests: groundedness, faithfulness, answer relevance, citation completeness.
- Security tests: RBAC leakage, helpdesk FIOD denial, cache isolation, prompt-injection resistance.
- Performance tests: p50/p95 TTFT, p95/p99 latency, OOM/memory pressure, burst/latency spike behavior.
- Gates: fast PR smoke, stronger main gate, full release gate.

## Stage 1 Implementation Best Practices

- Prioritize deterministic pytest tests before LLM-as-judge evaluation.
- Use DeepEval as the primary future evaluation framework, but do not require real LLM judge execution in Stage 1 unless explicitly requested.
- Test both positive and negative security paths.
- Required hard-fail checks: RBAC leakage count `0`, unauthorized citation count `0`, prompt injection success count `0`.
- Test generated citations are a subset of authorized retrieved chunks.
- Test every factual claim has document name, document id, article/section, and paragraph.
- Include a final Stage 1 report with met/partial/not-met status, evidence, run commands, test commands, limitations, and next steps.

