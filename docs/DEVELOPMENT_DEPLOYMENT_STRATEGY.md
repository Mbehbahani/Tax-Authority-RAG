# Development and Deployment Strategy

This strategy tells Claude Code/Opus how to approach implementation and validation without overbuilding. The assessment is architecture-first, so development should prove the design locally and use AWS only where it is essential or explicitly requested.

## Recommended Strategy: Hybrid Local-First

Use a hybrid approach:

```text
Local-first for application logic and tests.
AWS only for managed model APIs and optional service compatibility checks.
No full cloud deployment unless explicitly requested.
```

This is better than all-local or all-cloud for the assignment.

## Why Not All Local?

All-local development is cheap and fast, but it cannot fully validate:

- Bedrock model invocation behavior;
- Haiku vs Sonnet latency/cost;
- Cohere Embed/Rerank access;
- AWS IAM/profile setup;
- real Bedrock streaming behavior.

Use local mocks for most logic, but test Bedrock access separately when needed.

## Why Not All Cloud?

All-cloud development is closer to production, but for this assignment it is usually too much:

- higher cost;
- more setup time;
- more deployment complexity;
- risk of over-focusing on infrastructure instead of architecture;
- unnecessary Kubernetes/deployment detail.

The assignment asks for a concrete architecture and configuration, not a full production deployment.

## Recommended Stages

### Stage 0 — Repository Preparation

Already done.

Includes:

- project memory;
- module docs;
- test scenarios;
- sample corpus;
- sample requests;
- AWS CLI access guidance;
- `.env.example` and local `.env`;
- CI skeleton.

### Stage 1 — Local PoC with OpenSearch Compatibility

Run locally with Docker Compose and lightweight components.

Use locally:

- FastAPI;
- LangGraph or simple graph stub;
- sample corpus from [`sample_corpus`](../sample_corpus);
- sample requests from [`sample_requests`](../sample_requests);
- local Redis container or in-memory cache;
- local OpenSearch container if feasible;
- mock retrieval fallback only if local OpenSearch is too heavy or blocks progress;
- pytest/DeepEval-style tests.

Purpose:

- prove legal chunking;
- prove metadata preservation;
- prove RBAC-before-retrieval logic;
- prove OpenSearch-compatible mapping/query/filter contract;
- prove citation validation;
- prove CRAG state transitions;
- prove abstention behavior.

Do not use local PoC to claim real 20M+ chunk performance.

Recommended Stage 1 sub-steps:

```text
Stage 1A — Implement OpenSearch-compatible retrieval adapter, mapping contract, query contract, and mock fallback.
Stage 1B — Run local OpenSearch in Docker Compose if feasible and validate mapping/query compatibility.
```

If local OpenSearch cannot run on the laptop, keep the adapter and tests structured so the backend can be switched to OpenSearch without reworking application logic.

### Stage 2 — AWS API Compatibility Checks

Use AWS only for APIs that cannot be realistically mocked:

- Bedrock Claude Haiku/Sonnet invocation;
- Cohere Embed v4 invocation;
- Cohere Rerank 3.5 invocation;
- optional Titan embedding fallback;
- basic latency and model access checks.

Use [`docs/AWS_CLI_ACCESS.md`](AWS_CLI_ACCESS.md) only when the user explicitly asks to verify AWS access.

Purpose:

- confirm model access;
- compare Haiku vs Sonnet quality/latency/cost;
- confirm embedding/rerank API contracts;
- avoid surprises before final implementation.

### Stage 3 — Optional Managed-Service Smoke Test

Only if explicitly requested, use small AWS managed services:

- S3 bucket for sample corpus/artifacts;
- small Amazon OpenSearch test domain or serverless collection;
- ElastiCache Redis only if cache behavior must be tested in AWS;
- Lambda + API Gateway + Mangum or ECS/App Runner for API only if runtime deployment is requested.

Purpose:

- validate integration shape;
- measure realistic network latency;
- check IAM and VPC/security assumptions.

This is not required for the assessment unless the user asks.

### Stage 4 — Production Architecture Plan

Describe future production architecture but do not deploy it.

Recommended production path:

- FastAPI on Lambda + API Gateway + Mangum for lightweight/variable traffic;
- ECS Fargate or App Runner if cold starts, streaming, or sustained traffic require it;
- Bedrock for LLM/embedding/rerank APIs;
- OpenSearch Service for hybrid retrieval;
- ElastiCache Redis for semantic cache;
- S3 for raw corpus and artifacts;
- IAM least privilege;
- Secrets Manager/SSM;
- CloudWatch/OpenTelemetry.

No Kubernetes unless justified by explicit operational requirements.

## What Claude Code Should Do First

1. Build local logic and tests first.
2. Keep AWS calls behind interfaces/adapters.
3. Use mocks/fakes for local tests.
4. Use Bedrock calls only in explicit integration checks.
5. Avoid creating real AWS infrastructure unless explicitly requested.

## Recommended Answer for the Assignment

Use this phrasing:

```text
Development should be local-first with Docker Compose for FastAPI, Redis, sample corpus, and an OpenSearch-compatible retrieval adapter. Local OpenSearch should be used if feasible to validate mapping/query compatibility; a mock fallback is acceptable only when local machine limits block progress. AWS is used during development only for managed model API compatibility checks against Bedrock models such as Claude Haiku/Sonnet, Cohere Embed, and Cohere Rerank. Full AWS infrastructure deployment is optional and not required for the assessment. If deployment is later needed, use a light AWS path: Lambda + API Gateway + Mangum or ECS/App Runner for FastAPI, OpenSearch Service, ElastiCache Redis, S3, Bedrock, IAM, Secrets Manager/SSM, and CloudWatch/OpenTelemetry.
```

