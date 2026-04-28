# Stage 1 Implementation Report Template

Claude Code should create [`docs/reports/STAGE_1_IMPLEMENTATION_REPORT.md`](reports/STAGE_1_IMPLEMENTATION_REPORT.md) after completing Stage 1.

## 1. Executive Summary

Summarize what was built and whether Stage 1 is ready for review.

## 2. Goal Checklist

| Goal | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Legal-aware ingestion | Met / Partial / Not Met | file paths, tests |  |
| OpenSearch-compatible retrieval | Met / Partial / Not Met | file paths, tests |  |
| RBAC before retrieval | Met / Partial / Not Met | file paths, tests |  |
| Helpdesk FIOD denial | Met / Partial / Not Met | file paths, tests |  |
| CRAG state machine | Met / Partial / Not Met | file paths, tests |  |
| Citation completeness | Met / Partial / Not Met | file paths, tests |  |
| Abstention behavior | Met / Partial / Not Met | file paths, tests |  |
| FastAPI endpoints | Met / Partial / Not Met | file paths, tests |  |
| Local OpenSearch compatibility | Met / Partial / Not Met | file paths, tests |  |
| Deterministic tests | Met / Partial / Not Met | file paths, tests |  |

## 3. Distance From Targets

| Target | Expected | Actual | Distance / Gap | Notes |
| --- | --- | --- | --- | --- |
| RBAC leakage count | 0 | TBD | TBD |  |
| Citation completeness | 100% | TBD | TBD |  |
| Citation accuracy | 100% | TBD | TBD |  |
| TTFT p95 smoke target | < 1.5s | TBD | TBD |  |
| OOM events | 0 | TBD | TBD |  |
| Test pass count | all relevant tests | TBD | TBD |  |

## 4. What Was Built

List created/updated files and their purpose.

## 5. How to Run Locally

Include exact commands for installing dependencies, starting services, and running the API.

## 6. How to Run Tests

Include exact commands for unit, integration, security, eval, and performance smoke tests.

## 7. Where to Change Settings

| Setting | File | Notes |
| --- | --- | --- |
| Environment values | `.env` / `.env.example` | local/private vs template |
| Bedrock model IDs | `.env` / `.env.example` | generation, fast, judge, embedding, rerank |
| Retrieval top-k | `.env` / retrieval config | lexical/vector/fused/rerank/final |
| RBAC roles | `sample_requests/users.json` and security code | roles, clearance, scopes |
| Sample documents | `sample_corpus/` | synthetic corpus |
| Expected behavior | `sample_requests/expected_behaviors.json` | user/query expectations |
| Evaluation thresholds | `tests/eval/ci_eval_gates.json` | release gates |

## 8. Mocked or Local-Only Parts

Explain what is not yet real production infrastructure.

## 9. Known Limitations

List limitations, risks, and incomplete items.

## 10. Recommended Next Steps

State what should happen before final assessment writing and before any deployment.


