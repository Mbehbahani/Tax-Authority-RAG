# Prompt and Context Guide

This repository contains several docs, but Claude Code should not read everything every time. Use the smallest context needed.

## Stage 1 Implementation

Use [`prompts/STAGE_1_LOCAL_POC_PROMPT.md`](../prompts/STAGE_1_LOCAL_POC_PROMPT.md).

Core context:

- [`CLAUDE.md`](../CLAUDE.md)
- [`docs/PROJECT_BRIEF_FOR_CLAUDE_CODE.md`](PROJECT_BRIEF_FOR_CLAUDE_CODE.md)
- [`docs/DEVELOPMENT_DEPLOYMENT_STRATEGY.md`](DEVELOPMENT_DEPLOYMENT_STRATEGY.md)
- [`docs/LOCAL_POC_PLAN.md`](LOCAL_POC_PLAN.md)
- [`docs/MODULE_1_INGESTION.md`](MODULE_1_INGESTION.md)
- [`docs/MODULE_2_RETRIEVAL.md`](MODULE_2_RETRIEVAL.md)
- [`docs/MODULE_3_AGENTIC_RAG.md`](MODULE_3_AGENTIC_RAG.md)
- [`docs/MODULE_4_PRODUCTION_OPS.md`](MODULE_4_PRODUCTION_OPS.md)
- [`docs/TEST_STRATEGY.md`](TEST_STRATEGY.md)
- [`sample_corpus/README.md`](../sample_corpus/README.md)
- [`sample_requests/README.md`](../sample_requests/README.md)

Do not read personal notes for implementation.

Claude Code is not limited to existing placeholder files or scaffolding. It may refactor, add, remove, or reorganize implementation files when that improves the Stage 1 local PoC. It must preserve the project constraints and avoid deployment.

After Stage 1 implementation, Claude Code must create [`docs/STAGE_1_IMPLEMENTATION_REPORT.md`](STAGE_1_IMPLEMENTATION_REPORT.md) using [`docs/STAGE_1_REPORT_TEMPLATE.md`](STAGE_1_REPORT_TEMPLATE.md).

## AWS Verification Only

Use [`docs/AWS_CLI_ACCESS.md`](AWS_CLI_ACCESS.md) only when the user explicitly asks for AWS/Bedrock verification or when local limitations require managed model API checks.

## Final Assessment Writing Later

Use [`prompts/FINAL_ASSESSMENT_WRITING_PROMPT.md`](../prompts/FINAL_ASSESSMENT_WRITING_PROMPT.md) only after the local PoC is complete or when the user explicitly asks for the final written assessment.

## Avoid Over-Tokenizing

- Do not read every fixture file up front.
- Read fixture files only when implementing the related tests.
- Do not duplicate the same requirements in new docs.
- Prefer code and tests over more planning documents during Stage 1.

