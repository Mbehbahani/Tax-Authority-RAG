# Stage 1 Implementation Report

## 1. Executive Summary

Stage 1 builds a complete local PoC of the enterprise Tax Authority RAG
architecture (ingestion, hybrid retrieval, deterministic CRAG, FastAPI
surface, RBAC-before-retrieval, citation validation, authorization-scoped
semantic cache, and audit logging) that runs **entirely offline** against the
synthetic corpus and sample requests in this repository. No AWS APIs are
invoked, no infrastructure is deployed, and no secrets are created.

All core assessment constraints — zero-hallucination tolerance via exact
citations, RBAC-before-retrieval, helpdesk FIOD denial, bounded
correction/abstention, citation membership in the authorized context set —
are exercised by 75 deterministic pytest tests that complete in under a
second. The suite covers unit, integration (including the full OpenSearch
mapping/query contract), security (RBAC leakage, prompt injection,
cache isolation), RAG evaluation, and a performance smoke check.

The retrieval layer is implemented behind a single adapter with two
backends: an **OpenSearch-compatible in-memory fake** (used by default on a
laptop) and the **mapping/query contract** that can drive a real OpenSearch
cluster. Both backends share one authorization filter, so application-level
tests are backend-agnostic.

## 2. Goal Checklist

| Goal | Status | Evidence | Notes |
| --- | --- | --- | --- |
| Legal-aware ingestion (legislation + case law + policy + e-learning) | Met | [`app/rag/ingestion.py`](../app/rag/ingestion.py), [`tests/unit/test_ingestion_chunking.py`](../tests/unit/test_ingestion_chunking.py) | Chapter/Section/Article/Paragraph for legislation; ECLI + Facts/Legal Question/Reasoning/Holding for case law. |
| Front-matter metadata + lineage | Met | [`app/rag/models.py`](../app/rag/models.py), `test_every_chunk_has_citation_critical_metadata`, `test_restricted_fiod_metadata_preserved` | Stable `chunk_id`, classification, allowed_roles, effective_from/to, version, case_scope preserved. |
| OpenSearch-compatible retrieval adapter | Met | [`app/rag/retrieval.py`](../app/rag/retrieval.py) (`build_index_mapping`, `build_opensearch_queries`), `tests/integration/test_retrieval_queries.py` | Exact mapping/query payloads asserted against `tests/integration/opensearch_index_config_expected.json`. |
| BM25 + vector + RRF + rerank + final top-N | Met | `InMemoryOpenSearchBackend`, `reciprocal_rank_fusion`, `rerank`, `take_with_complete_citations`; [`tests/unit/test_rrf_and_rerank.py`](../tests/unit/test_rrf_and_rerank.py) | Field boosts `ecli^12 / document_id^8 / article^5 / text^2`; reranker cap 60; final context ≤ 8. |
| Exact identifier retrieval (ECLI) | Met | `test_exact_ecli_retrieves_case_law_for_inspector`, `test_ask_inspector_ecli_returns_case_law` | ECLI query surfaces DOC-CASE-001 for inspector/legal; never surfaces FIOD. |
| RBAC-before-retrieval | Met | [`app/rag/security.py`](../app/rag/security.py), `tests/security/test_rbac_and_injection.py` | `InMemoryOpenSearchBackend.lexical_search` / `vector_search` filter before scoring; leakage guard in `hybrid_retrieve`. |
| Helpdesk FIOD denial | Met | `test_helpdesk_cannot_retrieve_fiod`, `test_helpdesk_lexical_search_cannot_surface_fiod`, `test_helpdesk_vector_search_cannot_surface_fiod`, `test_helpdesk_fiod_query_returns_abstention` | FIOD docs never appear in lexical, vector, fused, reranked, or cited sets for helpdesk. |
| Deterministic CRAG state machine | Met | [`app/rag/graph.py`](../app/rag/graph.py), [`tests/unit/test_crag_state_transitions.py`](../tests/unit/test_crag_state_transitions.py) | All thirteen states implemented; bounded retrievals (2), rewrites (1), HyDE (1), decomposition cap (4). |
| Grader labels Relevant/Ambiguous/Irrelevant | Met | `grade_context`, `test_grader_returns_*` | Version-conflict detection flags 2023-year query as Ambiguous. |
| Citation completeness + membership | Met | [`app/rag/generation.py`](../app/rag/generation.py) (`all_citations_complete`, `citations_are_subset_of_context`), `test_every_citation_is_complete`, `test_every_citation_is_member_of_retrieved_context` | Every cited chunk id is guaranteed to be in the authorized retrieved set. |
| Abstention on unauthorized / version / retry-exhausted | Met | `test_missing_context_triggers_abstention`, `test_version_conflict_triggers_abstention`, `test_graph_rewrite_then_abstain_respects_retry_budget` | Abstention reason is surfaced on the API response. |
| Prompt-injection denial before retrieval | Met | `detect_prompt_injection`, `test_prompt_injection_blocks_before_retrieval`, `test_ask_injection_is_rejected_with_audit_reason` | Injection is detected in `CLASSIFY_QUERY`; `RETRIEVE` is never entered. |
| Semantic cache, authorization-scoped | Met | [`app/rag/cache.py`](../app/rag/cache.py), [`tests/security/test_semantic_cache_isolation.py`](../tests/security/test_semantic_cache_isolation.py) | Cache keys include scope hash, corpus version, embedding model version, citation ids hash. |
| Audit logging | Met | `app.rag.security.audit` called from `app.rag.service.RagService.ask` | JSON records for `cache_hit` and `rag_answer` with user, filters, retrieved chunk ids, citation ids, abstention reason, injection flag. |
| FastAPI `/health` and `/ask` | Met | [`app/main.py`](../app/main.py), [`tests/integration/test_api_endpoints.py`](../tests/integration/test_api_endpoints.py) | `/ask` loads user context from `sample_requests/users.json`, returns answer, citations, retrieved_chunk_ids, grader label, cache-hit flag, trace, latency. |
| Deterministic pytest suite (no live LLM) | Met | 75 tests pass in ~0.8s | Runs without AWS, without OpenSearch container, fully offline. |
| Local OpenSearch compatibility validation | Partial | Mapping + query contract asserted against expected fixture; live container not required to pass tests | Docker Compose profile `opensearch` is ready; live end-to-end validation against a running OpenSearch cluster is deferred to Stage 1B on a larger machine. |

## 3. Distance From Targets

| Target | Expected | Actual | Distance / Gap | Notes |
| --- | --- | --- | --- | --- |
| RBAC leakage count | 0 | 0 | 0 | Asserted across lexical, vector, fused, reranked, final, cited, and cached sets. |
| Citation completeness | 100 % | 100 % on the non-abstention path | 0 | Composer rejects incomplete citations; validation stage abstains if any cited chunk is outside the retrieved set. |
| Citation accuracy (chunk id ∈ authorized retrieved) | 100 % | 100 % | 0 | Guaranteed by construction — cites are built from the same chunk objects that reached generation. |
| Abstention correctness (FIOD denial + version conflict) | Abstain | Abstains with reason `retry_budget_exhausted` or `prompt_injection_detected` | none on the tested set | Reasons are surfaced for audit. |
| TTFT p95 (local in-memory, smoke) | < 1.5 s | p95 < 0.05 s | ~30× under budget | Production path replaces the fake with OpenSearch + Bedrock; the target is re-validated in Stage 1B/Stage 2. |
| OOM events | 0 | 0 | 0 | Corpus is tiny; the architectural controls that matter at 20M chunks (bounded top-k, ef_search cap, rerank cap, final-context cap) are enforced and tested. |
| Test pass count | all | **75 / 75 passing** | 0 | `pytest -v` output included in Section 6 below. |

## 4. What Was Built

### New application code

| File | Purpose |
| --- | --- |
| [`app/__init__.py`](../app/__init__.py) | Package marker. |
| [`app/main.py`](../app/main.py) | FastAPI app with lifespan-based warm-up, `/health`, `/ask` (rejects unknown users with 404). |
| [`app/rag/__init__.py`](../app/rag/__init__.py) | RAG package. |
| [`app/rag/models.py`](../app/rag/models.py) | `UserContext`, `Chunk`, `Citation`, `GraderResult` dataclasses; `Chunk.to_index_doc()` for OpenSearch bulk indexing. |
| [`app/rag/ingestion.py`](../app/rag/ingestion.py) | Front-matter parser, legal-aware chunkers for `legislation`, `case_law`, `internal_policy`, `elearning`; `ingest_corpus()` driver. |
| [`app/rag/embeddings.py`](../app/rag/embeddings.py) | Deterministic hash-based embedding model (stand-in for Cohere Embed v4). |
| [`app/rag/security.py`](../app/rag/security.py) | `AuthFilter` (produces the exact OpenSearch `bool` query fragment + stable scope hash), `is_authorized`, `authorized_only`, `audit`. |
| [`app/rag/retrieval.py`](../app/rag/retrieval.py) | `build_index_mapping`, `build_opensearch_queries`, `RetrievalBackend` protocol, `InMemoryOpenSearchBackend`, `reciprocal_rank_fusion`, `rerank`, `take_with_complete_citations`, `hybrid_retrieve`. |
| [`app/rag/generation.py`](../app/rag/generation.py) | Deterministic extractive answer composer with prompt-injection detection and citation completeness checks. |
| [`app/rag/graph.py`](../app/rag/graph.py) | CRAG state machine: `run_graph`, grader, rewrite, HyDE, decomposition, bounded retries. |
| [`app/rag/cache.py`](../app/rag/cache.py) | Authorization-scoped semantic cache with cosine similarity threshold and citation-aware keys. |
| [`app/rag/service.py`](../app/rag/service.py) | `RagService.ask` orchestrator, `load_users`, `build_service_from_paths`. |

### New tests

| File | Scope |
| --- | --- |
| [`tests/conftest.py`](../tests/conftest.py) | Shared fixtures: `corpus_chunks`, `embedder`, `backend`, `rag_service`, `users`. |
| [`tests/unit/test_ingestion_chunking.py`](../tests/unit/test_ingestion_chunking.py) | Legal chunking + metadata preservation. |
| [`tests/unit/test_rrf_and_rerank.py`](../tests/unit/test_rrf_and_rerank.py) | RRF stability, rerank cap, historical-version de-duplication. |
| [`tests/unit/test_crag_state_transitions.py`](../tests/unit/test_crag_state_transitions.py) | CRAG transitions, limits, abstention paths. |
| [`tests/integration/test_retrieval_queries.py`](../tests/integration/test_retrieval_queries.py) | OpenSearch mapping + query contract, authorized retrieval, bounded top-k, fixture-driven query expectations. |
| [`tests/integration/test_api_endpoints.py`](../tests/integration/test_api_endpoints.py) | FastAPI `/health` and `/ask` (including unknown-user 404 and injection abstention). |
| [`tests/security/test_rbac_and_injection.py`](../tests/security/test_rbac_and_injection.py) | RBAC leakage, FIOD case_scope, prompt injection, `rbac_llm_scenarios.json` S2 and S6. |
| [`tests/security/test_semantic_cache_isolation.py`](../tests/security/test_semantic_cache_isolation.py) | Authorization-scoped cache, no cross-role reuse, no caching of abstentions. |
| [`tests/eval/test_zero_hallucination.py`](../tests/eval/test_zero_hallucination.py) | Citation completeness, membership, version-conflict abstention, grader-fixture alignment. |
| [`tests/perf/test_perf_smoke.py`](../tests/perf/test_perf_smoke.py) | Local TTFT sanity check + cache-hit latency sanity check. |

### Updated infrastructure / config

| File | Change |
| --- | --- |
| [`requirements.txt`](../requirements.txt) | Added `httpx` (FastAPI TestClient transport). |
| [`docker-compose.test.yml`](../docker-compose.test.yml) | Redis always-on; `opensearch` moved behind an opt-in Compose profile so laptops without 2 GB headroom can still run `up`; app volume-mounted for reload. |
| [`Dockerfile`](../Dockerfile) | New minimal image (python:3.12-slim + app + sample data). |
| [`.env`](../.env) / [`.env.example`](../.env.example) | `RETRIEVAL_BACKEND=memory` knob added. All previous settings left intact. |

### Intentional deletions

Seven empty placeholder directories under `app/rag/` (`ingestion`, `retrieval`,
`graph`, `security`, `cache`, `evaluation`, `models`) were replaced with the
single-file modules above. This removes a future trap where Python would treat
the placeholder `models/` directory as a package and shadow `app/rag/models.py`.

## 5. How to Run Locally

### Native Python (recommended for Windows laptops)

```bash
# From repo root
python -m pip install --user -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Then:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"u_helpdesk_01\",\"query\":\"Can a taxpayer deduct home office expenses?\"}"
```

### Docker Compose (API + Redis)

```bash
docker compose -f docker-compose.test.yml up --build
```

### Docker Compose with local OpenSearch (opt-in; ~2 GB RAM)

```bash
docker compose -f docker-compose.test.yml --profile opensearch up --build
```

The API today uses `InMemoryOpenSearchBackend` regardless of whether the
OpenSearch container is running; switching to the real container is a wiring
change behind the adapter (see Section 10).

## 6. How to Run Tests

```bash
# Full suite (unit + integration + security + eval + perf smoke)
python -m pytest -q

# Verbose
python -m pytest -v

# Subsets
python -m pytest tests/unit
python -m pytest tests/integration
python -m pytest tests/security
python -m pytest tests/eval
python -m pytest tests/perf
```

Current run:

```text
75 passed in ~0.8s
```

Tests never require AWS, never require a running OpenSearch container, and
never call a live LLM. They use a deterministic embedding model and an
extractive answer composer whose outputs are structurally equivalent to what
a Bedrock-backed generator would produce under the same zero-hallucination
constraints.

## 7. Where to Change Settings

| Setting | File | Notes |
| --- | --- | --- |
| App env / log level / cache toggle / retrieval backend | [`.env`](../.env) and [`.env.example`](../.env.example) | `RETRIEVAL_BACKEND`, `SEMANTIC_CACHE_ENABLED`. |
| Bedrock model IDs (for later stages) | [`.env.example`](../.env.example) | `BEDROCK_GENERATION_MODEL_ID`, `BEDROCK_FAST_MODEL_ID`, `BEDROCK_EMBEDDING_MODEL_ID`, `BEDROCK_RERANK_MODEL_ID`. |
| Retrieval top-k / rerank cap / final top-n / ef_search | [`app/rag/retrieval.py`](../app/rag/retrieval.py) (module-level `DEFAULT_*`) + override via env wiring later | Current defaults match Module 2 (50/50/80/60/8/128). |
| RBAC roles, clearance, need-to-know | [`sample_requests/users.json`](../sample_requests/users.json) and [`app/rag/security.py`](../app/rag/security.py) | `build_auth_filter` encodes the role-to-tag policy. |
| Sample corpus | [`sample_corpus/`](../sample_corpus/) + [`sample_corpus/manifest.json`](../sample_corpus/manifest.json) | Add a new document by dropping a markdown file with front matter and registering it in `manifest.json`. |
| Query / expected-behavior fixtures | [`sample_requests/queries.json`](../sample_requests/queries.json), [`sample_requests/expected_behaviors.json`](../sample_requests/expected_behaviors.json) | Drive integration tests. |
| CI/CD evaluation gates | [`tests/eval/ci_eval_gates.json`](../tests/eval/ci_eval_gates.json) | Thresholds re-used in release gate design. |

## 8. Mocked or Local-Only Parts

| Component | What is real | What is mocked / local only | Replacement path |
| --- | --- | --- | --- |
| Embedding model | OpenSearch-compatible vector contract; cosine similarity | 128-d deterministic hash-based embeddings (`EmbeddingModel`) | Swap `EmbeddingModel.embed` for a Bedrock `cohere.embed-v4` / `titan-embed-text-v2` client. |
| Retrieval backend | `AuthFilter` → exact OpenSearch `bool` query body; full index mapping; identical field boosts | In-memory BM25 + cosine backend | Implement `RetrievalBackend.lexical_search` / `vector_search` against `opensearch-py` using `build_opensearch_queries`. |
| Reranker | Deterministic combination of RRF + identifier bonus + embedding similarity, capped at 60 | Not a real cross-encoder | Replace `rerank` with a Cohere Rerank 3.5 / cross-encoder call; the function signature is preserved. |
| LLM generation | Extractive composer that emits verbatim chunk quotes with exact citations | No Claude Haiku/Sonnet invocation | Replace `compose_answer` with a guarded Bedrock call whose prompt includes only authorized chunks and whose output goes through the same `validate_citations` stage. |
| Semantic cache | Authorization-scoped key; cosine-threshold lookup | In-memory list (not Redis) | Swap `SemanticCache` internals for `redis-py` with the same `lookup`/`write` API. |
| Audit logging | Structured JSON records via stdlib logging | Writes to the root logger | Point the `tax_rag.audit` logger at CloudWatch / OTel. |
| S3 raw corpus | Manifest-driven loader that reads markdown from disk | No S3 reads | Replace `load_manifest` and `parse_document` paths with an S3 client that streams from the raw bucket. |
| OpenSearch container | Docker Compose profile ready | Not wired into the app by default | Add an `OpenSearchBackend` class alongside `InMemoryOpenSearchBackend` and select via `RETRIEVAL_BACKEND`. |

## 9. Known Limitations

- The deterministic embeddings do not produce realistic semantic neighborhoods
  — e.g. "quantum spacetime taxation theorem" lexically shares only stop-like
  tokens with the corpus, which is why the grader labels it Irrelevant in one
  hop. This is the correct behavior for the PoC, but real semantic recall
  benchmarks need Cohere Embed.
- The reranker is deterministic but *not* a cross-encoder; numerical
  recall/precision ranking quality numbers are not meaningful until Cohere
  Rerank is plugged in.
- The OpenSearch backend is not exercised end-to-end against a running
  container in CI. The mapping/query contract tests guarantee that when the
  backend is switched, the API does not have to change — but a real cluster
  smoke test is still outstanding.
- Prompt-injection detection uses a small phrase list; it will not catch
  paraphrased or multilingual injections. Production needs a lexical +
  classifier + guardrail layer and a larger marker set.
- Performance targets (TTFT p95 < 1.5 s, p99 latency, OOM pressure, burst
  behaviour at 20M chunks) are **not** validated by local tests. Stage 1
  documents the architectural controls (bounded top-k, ef_search cap, rerank
  cap, final-context cap, no unbounded retries) and the `tests/perf` folder
  is scaffolded for load tests that belong to Stage 2.
- Query decomposition uses regex heuristics. A classifier-based decomposer is
  in scope for Stage 2.
- No real DeepEval evaluation is executed; the fixtures are in place so
  `deepeval` can be added once Bedrock is wired up.

## 10. Recommended Next Steps

1. **Stage 1B – real OpenSearch backend.** Add `OpenSearchBackend` next to
   `InMemoryOpenSearchBackend`, select via `RETRIEVAL_BACKEND=opensearch`, and
   run the existing integration tests against the Docker Compose `opensearch`
   profile. No application code changes required.
2. **Stage 2 – Bedrock compatibility checks.** Using
   [`docs/AWS_CLI_ACCESS.md`](AWS_CLI_ACCESS.md), verify model access for the
   five IDs in `.env.example`. Replace `EmbeddingModel` and `compose_answer`
   with Bedrock clients; keep the `validate_citations` stage unchanged.
3. **Real reranker.** Wire Cohere Rerank 3.5 into `rerank` and re-run the
   integration suite; the 60-candidate cap is already enforced.
4. **DeepEval run.** Execute the evaluation scenarios in
   `tests/eval/zero_hallucination_scenarios.json` against the Bedrock-backed
   generator; enforce the release gate thresholds in
   `tests/eval/ci_eval_gates.json`.
5. **Load / OOM validation.** Index a 1 M – 5 M synthetic chunk fanout into
   the OpenSearch container, tune shard count + `ef_search`, and re-run
   `tests/perf/full_perf.json` scenarios.
6. **Stronger injection defence.** Replace `detect_prompt_injection` with a
   classifier + role-aware guardrail before production traffic.

Stage 1 is ready for review and for writing the final assessment; it is **not**
ready for deployment.
