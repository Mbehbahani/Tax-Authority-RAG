# Running Modes — Tax Authority RAG PoC

This project exposes **two reviewer-facing runtime modes** that match the final
assignment report structure:

| Mode | Purpose | Compose file | Port |
| --- | --- | --- | --- |
| Stage A — Local PoC / Algorithm Validation | Fast deterministic validation, no AWS cost | `docker-compose.poc.yml` | `8000` |
| Stage B — Full Real Bedrock System | Real OpenSearch + Redis + LangGraph + Bedrock | `docker-compose.full.yml` | `8002` |

The older `docker-compose.test.yml` is kept as a legacy/compatibility file
because it was used during development and earlier optional tests. Reviewers
should use the two files above.

---

## Mode 1 — Stage A: Local PoC / Algorithm Validation

Use this mode to prove the algorithm and security behavior. It is fast,
deterministic, offline-safe, and does not require AWS credentials.

### What you get

| Component | Status |
| --- | --- |
| Retrieval | In-memory OpenSearch-compatible fake |
| Cache | Disabled / local deterministic path |
| Graph | Deterministic FSM |
| Embeddings | Local deterministic embeddings |
| Reranker | Deterministic reranker |
| Generation | Extractive citation-safe composer |
| AWS/Bedrock | Not used |

### Start command

```bash
docker compose -f docker-compose.poc.yml up --build api
```

### Access

```text
http://localhost:8000
```

### Best for

- Local development.
- Fast demonstrations of the API/frontend.
- Algorithm validation.
- RBAC and citation-safety behavior.
- CI-style test interpretation.

### Interpretation

This mode proves correctness and safety, but its latency is **not** real Bedrock
latency because it avoids external AWS model calls.

---

## Mode 2 — Stage B: Full Real Bedrock System

Use this mode for the most realistic production-shaped demo. It uses real Docker
infrastructure and real AWS Bedrock model calls.

### What you get

| Component | Status |
| --- | --- |
| Retrieval | Real OpenSearch Docker service |
| Cache | Real Redis Docker service |
| Graph | Real LangGraph StateGraph |
| Embeddings | Bedrock Cohere Embed v4: `eu.cohere.embed-v4:0` |
| Reranker | Bedrock Cohere Rerank 3.5: `cohere.rerank-v3-5:0` |
| Generation | Bedrock Claude Haiku 4.5: `eu.anthropic.claude-haiku-4-5-20251001-v1:0` |

### Prerequisites

1. AWS credentials available on the host in your normal AWS config directory:

   ```text
   C:\Users\<you>\.aws
   ```

   The compose file mounts this directory into the container as `/root/.aws` and
   uses:

   ```text
   AWS_PROFILE=default
   AWS_REGION=eu-central-1
   ```

2. Bedrock model access enabled in `eu-central-1` for:

   - `eu.cohere.embed-v4:0`
   - `cohere.rerank-v3-5:0`
   - `eu.anthropic.claude-haiku-4-5-20251001-v1:0`

### Start command

```bash
docker compose -f docker-compose.full.yml up --build api
```

### Access

```text
http://localhost:8002
```

### What happens on first boot

1. FastAPI starts.
2. The app ingests the synthetic corpus in `sample_corpus/`.
3. Chunks are embedded with real Bedrock Cohere Embed v4.
4. Vectors are indexed into real OpenSearch.
5. Queries use real OpenSearch, Redis, LangGraph, Bedrock Rerank, and Bedrock
   Claude generation.

### Smart indexing on startup

The full mode uses smart indexing:

```yaml
- OPENSEARCH_RECREATE_INDEX=false
```

On startup the app checks the persistent OpenSearch volume:

1. If the index already exists and contains documents, it reuses the index and
   skips document re-embedding.
2. If the index is missing or empty, it embeds the corpus with Bedrock and indexes
   it automatically.

This means normal `down` / `up --build` cycles do not waste Bedrock embedding
calls as long as the Docker volume is kept.

If you intentionally want a clean rebuild, either delete volumes with
`docker compose -f docker-compose.full.yml down -v` or temporarily set:

```yaml
- OPENSEARCH_RECREATE_INDEX=true
```

### Verified real results

The latest real run on port `8002` measured:

| Test | Result |
| --- | --- |
| Health check | OpenSearch + Redis + LangGraph + Bedrock Embed/Rerank/Claude active |
| Cold allowed query | `5.146s`, `4` citations, `cache_hit=False`, full CRAG trace |
| Repeated allowed query | `0.209s`, `cache_hit=True`, `CACHE_HIT -> END` |
| FIOD helpdesk denial | `1.483s`, `abstained=True`, `FIOD leak=False`, `citations=0` |

### Interpretation

Cold full Bedrock calls are slower because they include external AWS model
latency. Cache hits meet the `<1.5s` target comfortably. RBAC-denied queries
abstain safely with zero FIOD leakage.

---

## Runtime banner

The frontend banner shows which tools are active:

| Pill type | Meaning |
| --- | --- |
| Green pills | Real Docker services such as OpenSearch, Redis, LangGraph |
| Purple pills | Real Bedrock APIs |
| Grey pills | Local/deterministic/fake components |

In full mode, the expected active tools are:

```text
OpenSearch (real)
Redis (real cache)
LangGraph (real)
Bedrock Embeddings (eu.cohere.embed-v4:0)
Bedrock Rerank (cohere.rerank-v3-5:0)
Bedrock Generation (eu.anthropic.claude-haiku-4-5-20251001-v1:0)
```

---

## Quick command summary

| Goal | Command |
| --- | --- |
| Run local PoC | `docker compose -f docker-compose.poc.yml up --build api` |
| Run full real Bedrock stack | `docker compose -f docker-compose.full.yml up --build api` |
| Run offline tests | `python -m pytest tests/` |
| Run legacy/development compose | `docker compose -f docker-compose.test.yml ...` |
