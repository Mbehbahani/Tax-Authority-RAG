"""FastAPI entry point for the Tax Authority RAG local PoC.

Two endpoints:
  - GET  /health           liveness probe
  - POST /ask              run a single RAG query as a known user

User context is loaded from ``sample_requests/users.json`` on startup. The LLM
is replaced by a deterministic extractive composer (see app/rag/generation.py)
so the PoC runs entirely offline; to switch to Bedrock, replace the generation
adapter without changing this file.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .rag.service import build_service_from_paths


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / os.getenv("SAMPLE_CORPUS_MANIFEST", "sample_corpus/manifest.json")
USERS_PATH = ROOT / os.getenv("SAMPLE_USERS_FILE", "sample_requests/users.json")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _get_service()
    yield


app = FastAPI(title="Tax Authority RAG PoC", version="1.0.0", lifespan=lifespan)


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


@app.get("/health")
def health() -> dict[str, str]:
    service, users = _get_service()
    return {
        "status": "ok",
        "user_count": str(len(users or {})),
        "chunk_count": str(len(service.backend.chunks) if hasattr(service.backend, "chunks") else 0),
    }


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
