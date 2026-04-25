# Project Brief for Claude Code + Opus 4.7

## Scenario

The National Tax Authority is building a secure internal AI assistant for tax inspectors, legal counsel, and helpdesk staff. It must answer complex fiscal questions over legislation, case law, internal policies, and training material.

## Assignment

Produce a polished technical design for an enterprise RAG architecture over roughly 500,000 documents and potentially 20M+ chunks.

## Preferred Stack

- FastAPI API layer
- LangGraph deterministic CRAG orchestration
- OpenSearch hybrid lexical + vector retrieval
- S3 for raw documents and ingestion artifacts
- Redis conservative semantic cache
- Bedrock or another enterprise-approved model API
- DeepEval as the primary evaluation framework, with standard RAG metric definitions and OpenTelemetry/structured traces for observability
- GitHub Actions and Docker Compose

## Constraints

- Zero-hallucination tolerance.
- Every claim must cite document name, article, and paragraph.
- Strict RBAC before retrieval.
- Helpdesk cannot retrieve or generate from classified FIOD/fraud-investigation documents.
- TTFT target below 1.5 seconds.
- Address OOM risk, memory pressure, and latency spikes.

## Expected Final Output

Four modules: Ingestion & Knowledge Structuring, Retrieval Strategy, Agentic RAG & Self-Healing, and Production Ops/Security/Evaluation. Include architecture, configs, pseudo-code, tests, performance strategy, and conclusion.

If the assessment prompt requires OpenSearch as the primary engine and exact seven-module output, follow [`docs/OPENSEARCH_ASSESSMENT_STRUCTURE.md`](OPENSEARCH_ASSESSMENT_STRUCTURE.md). That structure covers index design, strict RBAC, hybrid retrieval, reranking, self-healing, semantic caching, and mandatory testing/validation.

Prepared test contracts are available for RBAC/LLM access, zero hallucination, and performance scale: [`docs/RBAC_LLM_TEST_SCENARIOS.md`](RBAC_LLM_TEST_SCENARIOS.md), [`docs/ZERO_HALLUCINATION_TEST_SCENARIOS.md`](ZERO_HALLUCINATION_TEST_SCENARIOS.md), and [`docs/PERFORMANCE_TEST_SCENARIOS.md`](PERFORMANCE_TEST_SCENARIOS.md).

A synthetic local sample corpus is available in [`sample_corpus/README.md`](../sample_corpus/README.md) with legislation, historical legislation, case law, policy, restricted FIOD material, and e-learning examples for test and PoC design.

Prepared sample request files are available in [`sample_requests/README.md`](../sample_requests/README.md) for pre-run validation of roles, queries, and expected outcomes.


## Prepared Workspace

This repository contains Claude commands, skills, documentation outlines, minimal app scaffolding, evaluation/performance fixtures, CI skeleton, sample corpus, sample requests, and local PoC placeholders.

## What Opus Should Do Next

Read [`CLAUDE.md`](../CLAUDE.md) and this brief, then expand the module documents into a final technical assessment. Implementation is useful but secondary to architecture. A local PoC can validate the approach, but full deployment is not required.

Operational note: if the user explicitly asks to verify local AWS CLI or Bedrock access, use [`docs/AWS_CLI_ACCESS.md`](AWS_CLI_ACCESS.md). Do not copy secrets into committed files.

Development/deployment strategy: follow [`docs/DEVELOPMENT_DEPLOYMENT_STRATEGY.md`](DEVELOPMENT_DEPLOYMENT_STRATEGY.md). Prefer local-first development and tests; use AWS only for explicit Bedrock/API compatibility checks or if deployment is requested.

Prompt files for the user are available in [`prompts/STAGE_1_LOCAL_POC_PROMPT.md`](../prompts/STAGE_1_LOCAL_POC_PROMPT.md) and [`prompts/FINAL_ASSESSMENT_WRITING_PROMPT.md`](../prompts/FINAL_ASSESSMENT_WRITING_PROMPT.md).

To avoid excessive context, follow [`docs/PROMPT_AND_CONTEXT_GUIDE.md`](PROMPT_AND_CONTEXT_GUIDE.md).

