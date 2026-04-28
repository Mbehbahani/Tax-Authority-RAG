"""FastAPI entry point for the Tax Authority RAG local PoC.

Endpoints:
  - GET  /              serve the chat frontend (app/static/index.html)
  - GET  /health        liveness probe + runtime info (which tools are active)
  - GET  /users         list available users and their roles
  - GET  /queries       sample queries from sample_requests/queries.json
  - GET  /expected      expected behaviors from sample_requests/expected_behaviors.json
  - POST /ask           run a single RAG query as a known user
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .rag.service import build_service_from_paths


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / os.getenv("SAMPLE_CORPUS_MANIFEST", "sample_corpus/manifest.json")
USERS_PATH = ROOT / os.getenv("SAMPLE_USERS_FILE", "sample_requests/users.json")
QUERIES_PATH = ROOT / os.getenv("SAMPLE_QUERIES_FILE", "sample_requests/queries.json")
EXPECTED_PATH = ROOT / os.getenv("SAMPLE_EXPECTED_BEHAVIORS_FILE", "sample_requests/expected_behaviors.json")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _get_service()
    yield


app = FastAPI(title="Tax Authority RAG PoC", version="1.0.0", lifespan=lifespan)

# Allow the HTML file to be opened directly from disk (file:// origin = null)
# as well as the normal http://localhost:8000 served path.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AskRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    query: str = Field(..., min_length=1, max_length=2000)


class CitationOut(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    article: str
    paragraph: str


class AskResponse(BaseModel):
    user_id: str
    query: str
    answer: str
    abstained: bool
    abstention_reason: str | None
    citations: list[CitationOut]
    retrieved_chunk_ids: list[str]
    grader_label: str | None
    cache_hit: bool
    latency_seconds: float
    trace: list[str]


_service = None
_users = None


def _get_service():
    global _service, _users
    if _service is None:
        _service, _users = build_service_from_paths(
            manifest_path=MANIFEST_PATH,
            users_path=USERS_PATH,
            enable_cache=os.getenv("SEMANTIC_CACHE_ENABLED", "false").lower() == "true",
        )
    return _service, _users


def _runtime_info() -> dict:
    """Return which real services / models are active in the current process."""
    def env_flag(name: str) -> bool:
        return os.getenv(name, "false").lower() == "true"

    retrieval_backend = os.getenv("RETRIEVAL_BACKEND", "memory")
    cache_backend = os.getenv("SEMANTIC_CACHE_BACKEND", "memory")
    graph_backend = os.getenv("RAG_GRAPH_BACKEND", "fsm")
    bedrock_embed = env_flag("BEDROCK_EMBEDDINGS_ENABLED")
    bedrock_rerank = env_flag("BEDROCK_RERANK_ENABLED")
    bedrock_gen = env_flag("BEDROCK_GENERATION_ENABLED")
    cache_enabled = env_flag("SEMANTIC_CACHE_ENABLED")

    tools_active = []
    if retrieval_backend == "opensearch":
        tools_active.append("OpenSearch (real)")
    else:
        tools_active.append("InMemory (fake)")

    if cache_enabled and cache_backend == "redis":
        tools_active.append("Redis (real cache)")
    elif cache_enabled:
        tools_active.append("InMemory cache")
    else:
        tools_active.append("Cache disabled")

    if graph_backend == "langgraph":
        tools_active.append("LangGraph (real)")
    else:
        tools_active.append("FSM graph (deterministic)")

    if bedrock_embed:
        tools_active.append(f"Bedrock Embeddings ({os.getenv('BEDROCK_EMBEDDING_MODEL_ID', 'eu.cohere.embed-v4:0')})")
    else:
        tools_active.append("Local embeddings (TF-IDF)")

    if bedrock_rerank:
        tools_active.append(f"Bedrock Rerank ({os.getenv('BEDROCK_RERANK_MODEL_ID', 'cohere.rerank-v3-5:0')})")
    else:
        tools_active.append("Deterministic reranker")

    if bedrock_gen:
        tools_active.append(f"Bedrock Generation ({os.getenv('BEDROCK_GENERATION_MODEL_ID', 'eu.anthropic.claude-3-7-sonnet-20250219-v1:0')})")
    else:
        tools_active.append("Extractive composer (no LLM)")

    return {
        "retrieval_backend": retrieval_backend,
        "cache_backend": cache_backend if cache_enabled else "disabled",
        "graph_backend": graph_backend,
        "bedrock_embeddings": bedrock_embed,
        "bedrock_rerank": bedrock_rerank,
        "bedrock_generation": bedrock_gen,
        "tools_active": tools_active,
    }


@app.get("/", include_in_schema=False)
def frontend() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parent / "static" / "index.html")


@app.get("/users")
def list_users() -> dict:
    _, users = _get_service()
    return {
        "users": [
            {
                "user_id": u.user_id,
                "role": u.role,
                "clearance": u.clearance,
            }
            for u in (users or {}).values()
        ]
    }


@app.get("/health")
def health() -> dict:
    service, users = _get_service()
    info = _runtime_info()
    return {
        "status": "ok",
        "user_count": len(users or {}),
        "chunk_count": len(service.backend.chunks) if hasattr(service.backend, "chunks") else 0,
        **info,
    }


@app.get("/queries")
def list_queries() -> dict:
    """Return sample queries from queries.json for the frontend to display."""
    if not QUERIES_PATH.exists():
        return {"queries": []}
    return json.loads(QUERIES_PATH.read_text(encoding="utf-8"))


@app.get("/expected")
def list_expected() -> dict:
    """Return expected behaviors from expected_behaviors.json for the frontend."""
    if not EXPECTED_PATH.exists():
        return {"expected_behaviors": []}
    return json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    service, users = _get_service()
    user = (users or {}).get(req.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"unknown user_id: {req.user_id}")

    result = service.ask(user, req.query)
    return AskResponse(
        user_id=result.user_id,
        query=result.query,
        answer=result.answer,
        abstained=result.abstained,
        abstention_reason=result.abstention_reason,
        citations=[CitationOut(**c) for c in result.citations],
        retrieved_chunk_ids=result.retrieved_chunk_ids,
        grader_label=result.grader_label,
        cache_hit=result.cache_hit,
        latency_seconds=result.latency_seconds,
        trace=result.trace,
    )
