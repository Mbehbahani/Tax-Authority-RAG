# Documentation Guide

Start here if you are reviewing the assignment.

## Recommended reading order

1. [`reports/FINAL_ASSIGNMENT_REPORT.md`](reports/FINAL_ASSIGNMENT_REPORT.md) — consolidated final report with clear separation between local PoC evidence and real Bedrock evidence.
2. [`reports/IMPLEMENTATION_AND_VALIDATION_OVERVIEW.md`](reports/IMPLEMENTATION_AND_VALIDATION_OVERVIEW.md) — merged overview replacing the older stage-by-stage implementation reports.
3. [`FINAL_TECHNICAL_ASSESSMENT_ANSWER.md`](FINAL_TECHNICAL_ASSESSMENT_ANSWER.md) — detailed architecture answer.
4. [`reports/ASSIGNMENT_ALIGNMENT_REPORT.md`](reports/ASSIGNMENT_ALIGNMENT_REPORT.md) — requirement-by-requirement coverage checklist.
5. [`RUNNING_MODES.md`](../RUNNING_MODES.md) — how to run the offline, local-real, and full Bedrock modes.

## How to interpret the reports

The project has two main evidence categories:

| Category | Meaning |
| --- | --- |
| Local PoC / deterministic reports | Prove algorithm correctness, RBAC, citation validation, CRAG behavior, and CI repeatability. These results are not real Bedrock latency. |
| Real Bedrock stack results | Prove integration with real OpenSearch, Redis, LangGraph, Bedrock Embed, Bedrock Rerank, and Bedrock Claude generation. These results include real external API latency. |

Do not compare local deterministic latency directly with full Bedrock latency.

## Supporting reports

- [`reports/IMPLEMENTATION_AND_VALIDATION_OVERVIEW.md`](reports/IMPLEMENTATION_AND_VALIDATION_OVERVIEW.md) — merged implementation and validation summary.
- [`PERFORMANCE_TEST_SCENARIOS.md`](PERFORMANCE_TEST_SCENARIOS.md) — performance target and benchmark plan.
- [`TEST_STRATEGY.md`](TEST_STRATEGY.md) — test matrix and CI/CD gates.
