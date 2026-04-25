# Local PoC Plan

## Corpus

Use a small synthetic corpus with legislation, one case-law document, one internal policy, and one classified FIOD-like document.

Prepared sample files are available in [`sample_corpus/README.md`](../sample_corpus/README.md) and indexed by [`sample_corpus/manifest.json`](../sample_corpus/manifest.json).

Prepared sample request files are available in [`sample_requests/README.md`](../sample_requests/README.md). Use them before running a local PoC to verify users, queries, and expected behavior.

## Components

- Docker Compose for local services.
- FastAPI endpoint for questions.
- LangGraph deterministic flow.
- Local OpenSearch if feasible; otherwise OpenSearch-compatible mock retrieval fallback.
- Optional Redis.
- Test users: helpdesk, inspector, legal counsel.

## Development Strategy

Use local-first development. Keep application logic, RBAC, chunking, citation validation, graph transitions, and tests local. Include OpenSearch compatibility from the first implementation stage by using an adapter, mapping/query contract tests, and local OpenSearch in Docker Compose if feasible. Use a mock fallback only if local OpenSearch is too heavy for the machine. Use AWS only for explicit Bedrock model API compatibility checks unless the user requests cloud deployment.

See [`docs/DEVELOPMENT_DEPLOYMENT_STRATEGY.md`](DEVELOPMENT_DEPLOYMENT_STRATEGY.md).

## Validation

- Chunking preserves article/paragraph citations.
- Retrieval returns authorized chunks only.
- Helpdesk cannot access FIOD content.
- CRAG grades evidence and abstains when needed.
- Answers include exact citations.

