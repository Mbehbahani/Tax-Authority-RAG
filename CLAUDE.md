# Claude Code Project Memory: Enterprise Tax Authority RAG

First read [`docs/PROJECT_BRIEF_FOR_CLAUDE_CODE.md`](docs/PROJECT_BRIEF_FOR_CLAUDE_CODE.md), then use this file as persistent project memory.

For prompt/context selection, use [`docs/PROMPT_AND_CONTEXT_GUIDE.md`](docs/PROMPT_AND_CONTEXT_GUIDE.md).

## Purpose

Prepare and later deliver a polished technical assessment for an enterprise Retrieval-Augmented Generation architecture for a National Tax Authority internal AI assistant serving tax inspectors, legal counsel, and helpdesk staff.

## Final Deliverable

The final answer should cover four modules:

1. Ingestion & Knowledge Structuring
2. Retrieval Strategy
3. Agentic RAG & Self-Healing
4. Production Ops, Security & Evaluation

It should be architecture-first, implementation-ready, and include configuration parameters, pseudo-code, security design, evaluation strategy, and performance/OOM/latency strategy.

If the final prompt requires OpenSearch as the primary engine with seven exact modules, use [`docs/OPENSEARCH_ASSESSMENT_STRUCTURE.md`](docs/OPENSEARCH_ASSESSMENT_STRUCTURE.md) and [`.claude/commands/write-final-assessment.md`](.claude/commands/write-final-assessment.md) as the output contract.

## Preferred Architecture

- API: FastAPI
- Orchestration: LangGraph deterministic CRAG/state machine
- Retrieval: OpenSearch hybrid lexical + vector retrieval
- Storage: S3 for raw documents and ingestion artifacts
- Cache: Redis conservative semantic caching
- LLM/Embeddings: Bedrock or another enterprise-approved API
- Evaluation: DeepEval as primary framework; standard RAG metric definitions; OpenTelemetry/structured traces for debugging and observability
- CI/CD: GitHub Actions
- Local validation: Docker Compose

## Non-Negotiable Constraints

- Zero-hallucination tolerance.
- Every claim must include exact citation: document name, article, paragraph.
- RBAC must be enforced before retrieval.
- Helpdesk users must not retrieve or generate from classified FIOD/fraud-investigation documents.
- Design for 500,000 documents and 20M+ chunks.
- TTFT target: below 1.5 seconds for cached or common paths where feasible.
- Explicitly discuss OOM risk, memory pressure, latency spikes, and graceful degradation.

## Boundaries

- Do not fully implement the final system unless explicitly requested.
- Do not deploy real cloud infrastructure.
- Do not call real AWS APIs.
- Do not create credentials.
- Do not over-focus on Kubernetes or production deployment; Kubernetes only if clearly justified.
- Consider light AWS infrastructure only when needed.

## Local AWS CLI Access Note

If the user explicitly asks to verify AWS/Bedrock model access or run local AWS CLI checks, use [`docs/AWS_CLI_ACCESS.md`](docs/AWS_CLI_ACCESS.md).

Never write or commit AWS access keys, secret access keys, or session tokens. Use the existing local AWS CLI profile/SSO/IAM configuration.

## Coding and Documentation Style

- Keep implementation scaffolding minimal and readable.
- Prefer deterministic workflows and testable components.
- Document exact defaults and tuning knobs.
- Use concise diagrams, tables, pseudo-code, and decision rationale.
- You may refactor, add, remove, or reorganize implementation files when it improves correctness, maintainability, or testability. Existing scaffolding is a starting point, not a restriction.

## Security Rules

- RBAC and classification filters must run before retrieval.
- Propagate `user_id`, roles, organization unit, clearance, and audit context through the graph.
- Never allow generation from unauthorized chunks.
- Include audit logging for retrieval, prompt construction, cache decisions, and answer citations.

## Testing Rules

- Include unit, integration, security, RAG evaluation, and performance tests.
- Test citation completeness and citation exactness.
- Test RBAC leakage and FIOD denial for helpdesk roles.
- Test TTFT, p95/p99 latency, OOM/memory pressure, and burst behavior.
- Separate PR, main, and release gates.

## Performance Targets

- TTFT target below 1.5 seconds where practical.
- Keep final context small: usually 5-8 chunks.
- Use bounded top-k, reranking caps, retry limits, streaming, timeouts, and circuit breakers.
- Use conservative semantic cache only when authorization scope and citation set are safe.

