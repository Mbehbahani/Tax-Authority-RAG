# Documentation Guide

Start here if you are reviewing the assignment.

## Recommended reading order

1. [`reports/FINAL_ASSIGNMENT_REPORT.md`](reports/FINAL_ASSIGNMENT_REPORT.md) — consolidated final report with clear separation between local PoC evidence and real Bedrock evidence.
2. [`FINAL_TECHNICAL_ASSESSMENT_ANSWER.md`](FINAL_TECHNICAL_ASSESSMENT_ANSWER.md) — detailed architecture answer.
3. [`reports/ASSIGNMENT_ALIGNMENT_REPORT.md`](reports/ASSIGNMENT_ALIGNMENT_REPORT.md) — requirement-by-requirement coverage checklist.
4. [`reports/STAGE_4_DEEPEVAL_AND_RETRIEVAL_QUALITY_REPORT.md`](reports/STAGE_4_DEEPEVAL_AND_RETRIEVAL_QUALITY_REPORT.md) — evaluation metrics and release-gate targets.
5. [`RUNNING_MODES.md`](../RUNNING_MODES.md) — how to run the offline, local-real, and full Bedrock modes.

## How to interpret the reports

The project has two main evidence categories:

| Category | Meaning |
| --- | --- |
| Local PoC / deterministic reports | Prove algorithm correctness, RBAC, citation validation, CRAG behavior, and CI repeatability. These results are not real Bedrock latency. |
| Real Bedrock stack results | Prove integration with real OpenSearch, Redis, LangGraph, Bedrock Embed, Bedrock Rerank, and Bedrock Claude generation. These results include real external API latency. |

Do not compare local deterministic latency directly with full Bedrock latency.

## Appendix reports

- [`reports/STAGE_1_IMPLEMENTATION_REPORT.md`](reports/STAGE_1_IMPLEMENTATION_REPORT.md) — offline/local PoC baseline.
- [`reports/STAGE_2_BEDROCK_COMPATIBILITY_REPORT.md`](reports/STAGE_2_BEDROCK_COMPATIBILITY_REPORT.md) — Bedrock compatibility and runtime model IDs.
- [`reports/STAGE_3_BEDROCK_RAG_EVALUATION_REPORT.md`](reports/STAGE_3_BEDROCK_RAG_EVALUATION_REPORT.md) — optional Bedrock RAG wiring and model-routing evolution.
- [`PERFORMANCE_TEST_SCENARIOS.md`](PERFORMANCE_TEST_SCENARIOS.md) — performance target and benchmark plan.
- [`TEST_STRATEGY.md`](TEST_STRATEGY.md) — test matrix and CI/CD gates.
