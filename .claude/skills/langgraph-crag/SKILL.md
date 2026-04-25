---
name: langgraph-crag
description: Guidance for deterministic LangGraph/CRAG orchestration, retrieval grading, bounded retries, query transformation, and abstention.
---

# Skill: LangGraph CRAG

Use this skill when designing deterministic corrective RAG orchestration.

## Guidance

- Model the flow as a deterministic state machine, not a free-form autonomous agent.
- Recommended flow: classify query -> decompose if needed -> retrieve -> rerank -> grade -> answer, rewrite, retry, or abstain.
- Retrieval grades: relevant, ambiguous, irrelevant.
- Add retry limits and bounded query rewrites.
- Abstain when evidence is insufficient, conflicting, unauthorized, or missing exact citations.
- Preserve audit state: user context, query, filters, retrieved chunk ids, grader scores, generated citations.

## Stage 1 Implementation Best Practices

- Implement a simple explicit state machine if LangGraph adds too much dependency overhead; preserve LangGraph-compatible state names.
- Keep user authorization context immutable through the graph.
- Make every state return structured data for tests and audit logs.
- HyDE/rewrite output is never evidence and must never be cited.
- Validate citations after generation; if validation fails, route to abstain.
- Use low retry limits: max retrieval attempts `2`, max rewrites `1`, max HyDE attempts `1`, max decomposition subqueries `4`.
- Prefer deterministic rule-based grading for Stage 1 tests; LLM judge can be added later with DeepEval if explicitly requested.

