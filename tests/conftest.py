"""Shared pytest fixtures for the Tax Authority RAG local PoC."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest_plugins = ("pytest_asyncio",)

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rag.embeddings import EmbeddingModel  # noqa: E402
from app.rag.ingestion import ingest_corpus  # noqa: E402
from app.rag.models import UserContext  # noqa: E402
from app.rag.retrieval import InMemoryOpenSearchBackend  # noqa: E402
from app.rag.service import RagService, load_users  # noqa: E402


MANIFEST_PATH = ROOT / "sample_corpus" / "manifest.json"
USERS_PATH = ROOT / "sample_requests" / "users.json"


@pytest.fixture(scope="session")
def corpus_chunks():
    return ingest_corpus(MANIFEST_PATH)


@pytest.fixture(scope="session")
def embedder():
    return EmbeddingModel()


@pytest.fixture()
def backend(corpus_chunks, embedder):
    return InMemoryOpenSearchBackend(corpus_chunks, embedder=embedder)


@pytest.fixture()
def rag_service(corpus_chunks, backend, embedder):
    return RagService(chunks=corpus_chunks, backend=backend, embedder=embedder)


@pytest.fixture(scope="session")
def users() -> dict[str, UserContext]:
    return load_users(USERS_PATH)
