# Final Assignment Report: Secure Enterprise RAG for the Tax Authority

## 1. Executive Summary

This report presents the project in the clearest reviewer-friendly structure:

1. **Stage A — Local PoC / Algorithm Validation**: proves the RAG algorithm,
   security model, citation guarantees, CRAG state machine, and test strategy in
   a deterministic/offline environment.
2. **Stage B — Real System / Bedrock Integration Validation**: proves the same
   architecture can run with real OpenSearch, Redis, LangGraph, and AWS Bedrock
   services.

This separation is important because the two stages answer different questions:

| Stage | Main question answered | Performance interpretation |
| --- | --- | --- |
| Local PoC | Is the algorithm correct, secure, citation-safe, and repeatable in CI? | Fast local latency only; not real Bedrock latency. |
| Real Bedrock system | Does the architecture work with real services and real model calls? | Real external API latency; must separate cold path from cache-hit path. |

The implementation satisfies the core assessment requirements: legal-aware
chunking, hybrid retrieval, RBAC-before-retrieval, citation validation,
corrective/agentic RAG behavior, authorization-scoped semantic caching, and
formal evaluation gates.

---

## 2. Architecture Overview

The system is a secure, citation-first enterprise RAG architecture for internal
Tax Authority users such as helpdesk staff, tax inspectors, legal counsel, and
FIOD investigators.

### Core guarantees

1. **Legal hierarchy is preserved before embedding**
   - Legislation is chunked by chapter, section, article, and paragraph.
   - Case law preserves ECLI, facts, legal question, reasoning, holding, and
     paragraph references.
   - Policies and e-learning documents preserve section/module hierarchy.

2. **RBAC is enforced before retrieval scoring**
   - Unauthorized documents are excluded before lexical search, vector search,
     fusion, reranking, prompt assembly, generation, and cache reuse.

3. **Retrieval is hybrid and bounded**
   - BM25 handles exact identifiers such as ECLI/article/document IDs.
   - Vector search handles semantic tax questions.
   - RRF combines sparse and dense results.
   - Reranking is bounded by a maximum candidate cap.

4. **CRAG controls generation**
   - The graph grades evidence as `Relevant`, `Ambiguous`, or `Irrelevant`.
   - It can rewrite, run HyDE, decompose, retry within limits, or abstain.
   - It does not hallucinate when evidence is insufficient.

5. **Every accepted answer is citation-validated**
   - Citations must include chunk ID, document ID, document name, article/section,
     and paragraph.
   - Every cited chunk must belong to the authorized retrieved context.

### Technology choices

| Layer | Choice |
| --- | --- |
| API | FastAPI |
| Orchestration | LangGraph-compatible CRAG state machine |
| Retrieval store | OpenSearch |
| Cache | Redis semantic cache |
| Embeddings in real mode | Bedrock Cohere Embed v4: `eu.cohere.embed-v4:0` |
| Reranking in real mode | Bedrock Cohere Rerank 3.5: `cohere.rerank-v3-5:0` |
| Generation in real demo | Bedrock Claude Haiku 4.5: `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Evaluation | Deterministic evaluation + DeepEval-ready metric framework |

> **Model note:** The target production policy can route high-risk legal answers
> to Claude Sonnet if available. In the currently validated AWS account, the
> Sonnet model was blocked as Legacy, so the real demo uses Claude Haiku 4.5 for
> generation.

---

## 3. Stage A — Local PoC / Algorithm Validation

### 3.1 Definition

Stage A is the deterministic local proof-of-concept. It validates the algorithmic
and security behavior without AWS cost, external model latency, or cloud
credentials.

Depending on the exact mode, it uses:

- In-memory or OpenSearch-compatible retrieval adapter.
- Deterministic/local embeddings.
- Deterministic reranking.
- Extractive citation-safe composer.
- Deterministic CRAG/FSM or LangGraph-compatible state transitions.
- Offline pytest suite.

### 3.2 Specification

Stage A validates the following behavior:

| Capability | Specification |
| --- | --- |
| Legal-aware ingestion | Preserve document name, document ID, source type, article/section, paragraph, version/effective dates, classification, allowed roles, stable chunk ID. |
| Hybrid retrieval | BM25 + vector retrieval with RRF fusion. |
| Exact identifier support | Strong ECLI/document/article boosts. |
| RBAC | Filter unauthorized content before lexical/vector scoring. |
| Reranking | Bounded rerank candidate set. |
| Final context | Citation-complete chunks only, final context capped. |
| CRAG | `START -> AUTH_CONTEXT -> CLASSIFY_QUERY -> RETRIEVE -> RERANK -> GRADE_CONTEXT -> ... -> END`. |
| Fallbacks | Rewrite, HyDE, decomposition, bounded retries, abstention. |
| Citations | Complete citations and citation membership validation. |
| Cache security | Role/clearance/corpus/citation-scoped semantic cache keys. |
| Prompt injection | Injection is detected before retrieval. |

### 3.3 Stage A test results

The latest consolidated offline validation evidence from the existing reports is:

| Evidence | Result | Source |
| --- | ---: | --- |
| Stage 1 initial deterministic suite | `75 passed, 3 skipped` | `STAGE_1_IMPLEMENTATION_REPORT.md` |
| Stage 2 offline suite | `83 passed, 6 skipped` | `STAGE_2_BEDROCK_COMPATIBILITY_REPORT.md` |
| Stage 3 offline suite | `90 passed, 7 skipped` | `STAGE_3_BEDROCK_RAG_EVALUATION_REPORT.md` |
| Stage 4 offline suite | `97 passed, 9 skipped` | `STAGE_4_DEEPEVAL_AND_RETRIEVAL_QUALITY_REPORT.md` |
| Live local OpenSearch optional tests | `3 passed` | `STAGE_1_IMPLEMENTATION_REPORT.md` / `ASSIGNMENT_ALIGNMENT_REPORT.md` |
| RBAC leakage | `0` | Security/eval tests |
| Citation completeness | `100% on accepted answers` | Eval tests |
| Citation accuracy | `100% cited chunks are retrieved/authorized` | Eval tests |

### 3.4 Stage A interpretation

Stage A proves correctness and safety:

- The algorithm enforces RBAC before retrieval.
- Helpdesk users cannot retrieve or cite FIOD content.
- The system abstains when relevant evidence is unavailable or unauthorized.
- Accepted answers are citation-complete and grounded in authorized context.
- The CRAG state machine behaves deterministically and within retry budgets.

Stage A latency is useful for CI sanity checks, but it should **not** be reported
as real Bedrock latency because Stage A does not call external AWS models.

---

## 4. Stage B — Real System / Bedrock Integration Validation

### 4.1 Definition

Stage B is the real-service validation path. It demonstrates that the same
architecture works with live local infrastructure and real AWS Bedrock model
invocations.

The real stack runs on:

```text
http://localhost:8002
```

Start command:

```bash
docker compose -f docker-compose.test.yml --profile bedrock up --build api-bedrock -d
```

### 4.2 Specification

The `/health` endpoint confirms the following active tools:

| Component | Active real implementation |
| --- | --- |
| Retrieval | OpenSearch real |
| Cache | Redis real cache |
| Graph | LangGraph real |
| Embeddings | Bedrock `eu.cohere.embed-v4:0` |
| Rerank | Bedrock `cohere.rerank-v3-5:0` |
| Generation | Bedrock `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |

The real stack also includes a retry/backoff wrapper around Bedrock model calls
to handle AWS `ThrottlingException` responses.

### 4.3 Stage B real test results

These measurements were run against the active real Bedrock stack on port `8002`.

#### Health check

```json
{
  "status": "ok",
  "retrieval_backend": "opensearch",
  "cache_backend": "redis",
  "graph_backend": "langgraph",
  "bedrock_embeddings": true,
  "bedrock_rerank": true,
  "bedrock_generation": true,
  "tools_active": [
    "OpenSearch (real)",
    "Redis (real cache)",
    "LangGraph (real)",
    "Bedrock Embeddings (eu.cohere.embed-v4:0)",
    "Bedrock Rerank (cohere.rerank-v3-5:0)",
    "Bedrock Generation (eu.anthropic.claude-haiku-4-5-20251001-v1:0)"
  ]
}
```

#### Real allowed query — cold path

Query:

```text
What records must a taxpayer keep for home office claims in the latest guidance?
```

| Field | Result |
| --- | ---: |
| Abstained | `False` |
| Grader label | `Relevant` |
| Citations | `4` |
| Cache hit | `False` |
| Latency | `5.146s` |
| Trace | `START -> AUTH_CONTEXT -> CLASSIFY_QUERY -> RETRIEVE -> RERANK -> GRADE_CONTEXT -> GENERATE_WITH_CITATIONS -> VALIDATE_CITATIONS -> END` |

Interpretation: this is the full cold real pipeline: Bedrock embedding,
OpenSearch retrieval, Bedrock reranking, LangGraph execution, Bedrock Claude
generation, and citation validation.

#### Real allowed query — cached path

Same query repeated:

| Field | Result |
| --- | ---: |
| Abstained | `False` |
| Grader label | `Relevant` |
| Citations | `4` |
| Cache hit | `True` |
| Latency | `0.209s` |
| Trace | `CACHE_HIT -> END` |

Interpretation: Redis semantic cache works and satisfies the `<1.5s` target for
repeated/similar FAQ-style traffic.

#### Real RBAC/FIOD denial test

Query:

```text
Summarize fraud investigation insights for home office deduction abuse.
```

User:

```text
u_helpdesk_01
```

| Field | Result |
| --- | ---: |
| Abstained | `True` |
| Reason | `retry_budget_exhausted` |
| FIOD leak | `False` |
| Citations | `0` |
| Cache hit | `False` |
| Latency | `1.483s` |
| Trace | `START -> AUTH_CONTEXT -> CLASSIFY_QUERY -> RETRIEVE -> RERANK -> GRADE_CONTEXT -> HYDE_QUERY -> RETRIEVE -> RERANK -> GRADE_CONTEXT -> ABSTAIN -> END` |

Interpretation: the system correctly excluded FIOD evidence for a helpdesk user,
attempted one recovery path through HyDE, then abstained with zero leakage.

### 4.4 Stage B interpretation

The real system proves production-shaped integration:

- Real Bedrock models can be called successfully.
- Real OpenSearch and Redis are integrated into the RAG service.
- LangGraph executes the CRAG flow.
- Bedrock-generated answers remain citation-validated.
- RBAC still prevents unauthorized FIOD leakage.
- Real cache hits are fast enough for the `<1.5s` latency target.

The cold real Bedrock path is slower than the target because it includes multiple
external model calls. This should be reported transparently as cloud-model
latency, not as an algorithmic failure.

---

## 5. Performance Discussion

### 5.1 Why PoC latency and real Bedrock latency differ

The PoC path is deterministic and local, so it avoids network and external model
latency. The real Bedrock path includes:

1. Bedrock query embedding.
2. OpenSearch hybrid retrieval.
3. Bedrock Cohere reranking.
4. Bedrock Claude generation.
5. Citation validation and response assembly.

Therefore, the correct performance story is:

| Path | Measured latency | Interpretation |
| --- | ---: | --- |
| Local deterministic PoC | Very low local latency | CI/algorithm baseline only. |
| Full Bedrock cold path | `5.146s` | Real external API path; optimization needed for strict cold TTFT. |
| Full Bedrock cache hit | `0.209s` | Meets `<1.5s` target for repeated/similar queries. |
| RBAC denied path | `1.483s` | Secure abstention with no leakage. |

### 5.2 How to meet the `<1.5s` requirement

The current evidence supports this statement:

> The `<1.5s` latency target is achieved for authorization-safe cache hits and
> RBAC-denied abstention. Cold Bedrock generation currently measures around
> five seconds in the local demo because it depends on external Bedrock model
> calls. Production release should measure streaming TTFT separately and optimize
> cold-path latency with provisioned throughput, reduced rerank candidates,
> pre-warmed cache entries, and model/provider latency tuning.

Recommended optimizations for production:

- Stream generation and measure TTFT rather than full response time.
- Pre-warm Redis semantic cache for common helpdesk/tax FAQ queries.
- Reduce rerank candidate count for low-risk FAQ queries.
- Use provisioned throughput or higher Bedrock quotas for selected models.
- Use model routing: cheaper/faster Haiku for low-risk, stronger Sonnet for
  high-risk if available.
- Track p50/p95/p99 separately for cold, warm, cached, and denied paths.

---

## 6. Security and Zero-Hallucination Guarantees

| Requirement | Evidence |
| --- | --- |
| Helpdesk cannot access FIOD | Real test: `FIOD leak=False`; PoC security tests also validate this. |
| Unauthorized context never reaches generation | RBAC is applied before retrieval/fusion/rerank/prompt/generation/cache. |
| Citation completeness | Accepted answers include complete citation metadata. |
| Citation accuracy | Citations must be members of the authorized retrieved context. |
| No answer without evidence | CRAG abstains when evidence is insufficient or unauthorized. |
| Prompt injection resistance | Injection detection blocks retrieval before context is assembled. |
| Cache isolation | Cache keys include authorization/corpus/citation scope. |

The FIOD real-system test is particularly important because it proves that even
with real Bedrock rerank/generation enabled, restricted documents are not leaked.

---

## 7. Limitations and How to Address Them

The current project is stronger than a pure architecture sketch: it includes a
working local PoC, a real Bedrock-backed stack, a Terraform skeleton, and a
minimal real AWS smoke deployment. However, it is still **not yet a full
production-scale deployment** over a 500,000-document or 20M+ chunk corpus.

### 7.1 Latency limitation

**Current limitation:**

- Cold full-path Bedrock requests are slower than the strict `<1.5s` TTFT target.
- The local real demo measured about `5.146s` for a cold allowed query.
- The `<1.5s` target is currently demonstrated only for cache-hit or fast abstention paths.

**Why this happens:**

- Bedrock embedding call
- OpenSearch retrieval
- Bedrock reranking call
- Bedrock generation call
- final citation validation

**How to address it:**

1. Stream output and measure **streaming TTFT** separately from total response latency.
2. Pre-warm common FAQ cache entries in Redis.
3. Reduce rerank candidate size for low-risk/common questions.
4. Use faster model routing for low-risk traffic.
5. Tune Bedrock quotas / provisioned throughput where justified.
6. Deploy the full stack closer to Bedrock/OpenSearch in AWS to reduce network overhead.

### 7.2 Scale limitation

**Current limitation:**

- The architecture is designed for large scale, but the current validation corpus is still small.
- It does not yet prove flawless behavior over 500,000 documents or 20M+ chunks.

**Why this matters:**

- larger corpora increase near-duplicates,
- outdated vs. current law conflicts become more frequent,
- retrieval precision/recall becomes harder,
- index tuning and shard sizing become operationally important.

**How to address it:**

1. Run large synthetic/sanitized corpus benchmarks.
2. Measure recall/precision over much larger retrieval sets.
3. Tune OpenSearch shard count, HNSW parameters, and rerank caps.
4. Add stronger version-aware and date-aware retrieval evaluation.

### 7.3 Evaluation limitation

**Current limitation:**

- The project is **DeepEval-ready**, but the running local evaluator is still partly deterministic/proxy-based.
- Some formal metrics such as full judge-scored Context Precision are not yet being run in an always-on local CI path.

**Why this was done intentionally:**

- deterministic CI is cheaper, faster, and more stable,
- LLM-judge evaluation adds cost and variability,
- for a PoC, safety invariants were prioritized first.

**How to address it:**

1. Enable paid/full DeepEval judge runs for release-grade evaluations.
2. Run broader scenario suites with live model judging.
3. Keep deterministic CI gates for daily development, but add a stronger release gate path.

### 7.4 Deployment limitation

**Current limitation:**

- The project now has a Terraform skeleton and a real AWS smoke test, but not a full managed runtime deployment.
- The AWS smoke test created and verified baseline resources only:
  - S3 bucket
  - CloudWatch log group
  - ECS cluster

**What is still missing for full cloud deployment:**

- managed OpenSearch provisioning and runtime wiring,
- Redis/ElastiCache provisioning,
- ECS task definition and service,
- IAM task roles and least-privilege policies,
- secret injection via Secrets Manager or SSM,
- end-to-end deployed API runtime validation.

**How to address it:**

1. Install Terraform locally and run `fmt`, `validate`, and `plan`.
2. Extend the Terraform skeleton into ECS service/task + security + secrets.
3. Provision managed OpenSearch and Redis.
4. Deploy the containerized API into AWS and run the same retrieval/security tests there.

### 7.5 Model governance and portability limitation

**Current limitation:**

- The architecture is correct, but the **model-routing policy should not depend on a single named model assumption**.
- In enterprise environments, approved generation models can change over time because of provider lifecycle changes, regional availability, procurement rules, or governance decisions.
- Therefore, a production-ready process must validate the **capability class** of the model path (fast/low-cost vs. high-reasoning) rather than hard-coding the operational plan around one specific model name.

**How to address it structurally:**

1. Treat model selection as a **governed runtime configuration**, not as a fixed architectural dependency.
2. Define routing in terms of roles such as:
   - **fast generation model** for low-risk/helpdesk-style queries,
   - **high-reasoning model** for complex legal interpretation,
   - **judge/evaluation model** for offline release validation.
3. Keep model IDs externalized in configuration and verify them during deployment readiness checks.
4. Require a small compatibility gate before release:
   - model invokable,
   - latency within target band,
   - evaluation thresholds passed,
   - citation and RBAC guarantees unchanged.

**Practical result:**

This makes the system more professional and resilient: the architecture remains
stable even if a specific provider model is replaced by another approved model
with equivalent capability.

### 7.6 Honest final assessment

The correct final position is:

- the system design is **concrete enough for a DevOps/AI engineering team to begin implementation immediately**,
- the project has **partial real AWS validation**, not just local Docker proof,
- but several production-grade steps remain before claiming full-scale operational readiness.

That is a strength, not a weakness: the report now clearly separates **what is already proven** from **what should be done next**.

---

## 8. Mapping of Existing Reports

Use the existing documents as appendices/evidence, not as separate competing
final stories.

| Existing document | How to use it now |
| --- | --- |
| `FINAL_TECHNICAL_ASSESSMENT_ANSWER.md` | Main architecture details and module-by-module design. |
| `ASSIGNMENT_ALIGNMENT_REPORT.md` | Requirement coverage checklist. |
| `STAGE_1_IMPLEMENTATION_REPORT.md` | Appendix for deterministic/offline PoC evidence. |
| `STAGE_2_BEDROCK_COMPATIBILITY_REPORT.md` | Appendix for Bedrock model compatibility and runtime ID findings. |
| `STAGE_3_BEDROCK_RAG_EVALUATION_REPORT.md` | Appendix for feature-flag wiring and Bedrock graph validation. |
| `STAGE_4_DEEPEVAL_AND_RETRIEVAL_QUALITY_REPORT.md` | Appendix for formal evaluation metrics and release-gate targets. |
| `RUNNING_MODES.md` | Reproduction guide for Mode 1, Mode 2, and Mode 3. |
| `PERFORMANCE_TEST_SCENARIOS.md` | Performance benchmark plan and production targets. |
| `TEST_STRATEGY.md` | Test strategy and CI/CD gate definitions. |

Reviewer reading order:

1. This report: `FINAL_ASSIGNMENT_REPORT.md`.
2. `FINAL_TECHNICAL_ASSESSMENT_ANSWER.md` for detailed architecture.
3. `ASSIGNMENT_ALIGNMENT_REPORT.md` for requirement mapping.
4. Stage reports as appendices.
