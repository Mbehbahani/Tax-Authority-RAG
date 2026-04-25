# Architecture Plan

## Executive Architecture

FastAPI receives authenticated requests, LangGraph orchestrates deterministic CRAG, OpenSearch performs RBAC-filtered hybrid retrieval, Redis provides conservative cache, and an enterprise LLM API generates citation-grounded answers.

## Runtime Path

Authenticate -> authorize -> normalize query -> classify/decompose -> RBAC-filtered retrieval -> fusion -> rerank -> grade evidence -> answer/rewrite/abstain -> audit.

## Offline Ingestion Path

S3 raw documents -> parse -> normalize -> legal-aware chunking -> metadata enrichment -> embeddings -> OpenSearch indexing -> evaluation dataset refresh.

## Security Boundary

Authorization context is applied before retrieval and before cache lookup. Unauthorized chunks must never enter prompts.

## Cache Strategy

Use Redis only for high-confidence, authorization-scoped, citation-stable responses. Cache key includes query fingerprint, role scope, classification scope, corpus version, and citation ids.

## Evaluation Path

Run smoke evals in PR/main and full evals before release. Track groundedness, citations, RBAC leakage, retrieval quality, TTFT, latency, and memory.

## Local PoC Path

Use Docker Compose with FastAPI, local OpenSearch or mock retrieval, optional Redis, small sample corpus, and tests.

## Optional AWS Path

Future path: S3, OpenSearch Service, Bedrock, optional ElastiCache, optional ECS Fargate, IAM, Secrets Manager/SSM, CloudWatch.

