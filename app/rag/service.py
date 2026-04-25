"""High-level orchestrator: cache -> CRAG graph -> audit.

Encapsulates the ``answer_question`` pseudo-code from Module 4 so the FastAPI
layer only deals with HTTP concerns.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cache import SemanticCache
from .embeddings import EmbeddingModel
from .generation import detect_prompt_injection
from .graph import GraphDeps, RagState, run_graph
from .ingestion import ingest_corpus
from .models import Chunk, UserContext
from .retrieval import DEFAULT_INDEX_NAME, InMemoryOpenSearchBackend, OpenSearchBackend, RetrievalBackend
from .security import audit, build_auth_filter


DEFAULT_EMBEDDING_MODEL_VERSION = "local-deterministic-v1"
DEFAULT_CORPUS_VERSION = "synthetic-v1"


@dataclass
class AskResult:
    user_id: str
    query: str
    answer: str
    abstained: bool
    abstention_reason: str | None
    citations: list[dict[str, str]]
    retrieved_chunk_ids: list[str]
    grader_label: str | None
    cache_hit: bool
    latency_seconds: float
    trace: list[str]


class RagService:
    def __init__(
        self,
        *,
        chunks: list[Chunk],
        backend: RetrievalBackend | None = None,
        embedder: Any | None = None,
        cache: SemanticCache | None = None,
        corpus_version: str = DEFAULT_CORPUS_VERSION,
        embedding_model_version: str = DEFAULT_EMBEDDING_MODEL_VERSION,
        reranker: Any | None = None,
        answer_composer: Any | None = None,
        generation_model_version: str = "deterministic-extractive-v1",
    ) -> None:
        self._embedder = embedder or EmbeddingModel()
        self._backend = backend or InMemoryOpenSearchBackend(chunks, embedder=self._embedder)
        self._chunks = chunks
        self._cache = cache or SemanticCache(embedder=self._embedder, enabled=False)
        self._corpus_version = corpus_version
        self._embedding_model_version = embedding_model_version
        self._reranker = reranker
        self._answer_composer = answer_composer
        self._generation_model_version = generation_model_version

    # -----------------------------------------------------------------

    @property
    def cache(self) -> SemanticCache:
        return self._cache

    @property
    def backend(self) -> RetrievalBackend:
        return self._backend

    # -----------------------------------------------------------------

    def ask(self, user: UserContext, query: str) -> AskResult:
        start = time.perf_counter()
        auth = build_auth_filter(user)

        injection = detect_prompt_injection(query)

        # Cache lookup (authorization-scoped, injection-safe).
        if not injection:
            cached = self._cache.lookup(
                query,
                user,
                corpus_version=self._corpus_version,
                embedding_model_version=self._embedding_model_version,
                auth=auth,
            )
            if cached is not None:
                audit(
                    "cache_hit",
                    user_id=user.user_id,
                    role=user.role,
                    query=query,
                    citation_ids=[c.chunk_id for c in cached.citations],
                )
                elapsed = time.perf_counter() - start
                return AskResult(
                    user_id=user.user_id,
                    query=query,
                    answer=cached.answer_text,
                    abstained=False,
                    abstention_reason=None,
                    citations=[_citation_to_dict(c) for c in cached.citations],
                    retrieved_chunk_ids=[c.chunk_id for c in cached.citations],
                    grader_label="Relevant",
                    cache_hit=True,
                    latency_seconds=elapsed,
                    trace=["CACHE_HIT", "END"],
                )

        # CRAG execution.
        deps = GraphDeps(
            backend=self._backend,
            embedder=self._embedder,
            reranker=self._reranker,
            answer_composer=self._answer_composer,
        )
        state = run_graph(user=user, query=query, deps=deps)

        answer_text = state.answer.text if state.answer else ""
        abstained = bool(state.answer and state.answer.abstained) or not state.answer
        abstention_reason = state.abstention_reason if abstained else None
        citations = state.citations

        # Cache write: only when the answer has a complete, authorized citation
        # set and no prompt injection was detected.
        if not abstained and citations and not injection:
            self._cache.write(
                query,
                user,
                answer_text,
                citations,
                corpus_version=self._corpus_version,
                embedding_model_version=self._embedding_model_version,
                auth=auth,
                is_cache_safe=True,
            )

        audit(
            "rag_answer",
            user_id=user.user_id,
            role=user.role,
            query=query,
            retrieved_chunk_ids=[c.chunk_id for c in state.reranked_chunks],
            citation_ids=[c.chunk_id for c in citations],
            grader_label=state.grader.label if state.grader else None,
            abstained=abstained,
            abstention_reason=abstention_reason,
            injection_detected=injection,
            embedding_model_version=self._embedding_model_version,
            generation_model_version=self._generation_model_version,
        )

        elapsed = time.perf_counter() - start
        return AskResult(
            user_id=user.user_id,
            query=query,
            answer=answer_text,
            abstained=abstained,
            abstention_reason=abstention_reason,
            citations=[_citation_to_dict(c) for c in citations],
            retrieved_chunk_ids=[c.chunk_id for c in state.reranked_chunks],
            grader_label=state.grader.label if state.grader else None,
            cache_hit=False,
            latency_seconds=elapsed,
            trace=list(state.trace),
        )


# ---------------------------------------------------------------------------
# Loaders


def load_users(path: Path) -> dict[str, UserContext]:
    data = json.loads(path.read_text(encoding="utf-8"))
    users: dict[str, UserContext] = {}
    for entry in data.get("users", []):
        users[entry["user_id"]] = UserContext(
            user_id=entry["user_id"],
            role=entry["role"],
            clearance=int(entry["clearance"]),
            department_scope=tuple(entry.get("department_scope", [])),
            need_to_know_groups=tuple(entry.get("need_to_know_groups", [])),
        )
    return users


def build_service_from_paths(
    *,
    manifest_path: Path,
    users_path: Path | None = None,
    enable_cache: bool = False,
    retrieval_backend: str | None = None,
) -> tuple[RagService, dict[str, UserContext]]:
    chunks = ingest_corpus(manifest_path)
    embedder, embedding_model_version = _build_embedder_from_env()
    reranker = _build_reranker_from_env()
    answer_composer, generation_model_version = _build_answer_composer_from_env()
    backend_name = (retrieval_backend or os.getenv("RETRIEVAL_BACKEND", "memory")).lower()
    if backend_name == "opensearch":
        backend = OpenSearchBackend(
            chunks,
            embedder=embedder,
            url=os.getenv("OPENSEARCH_URL") or None,
            index_name=os.getenv("OPENSEARCH_INDEX", DEFAULT_INDEX_NAME),
            recreate_index=os.getenv("OPENSEARCH_RECREATE_INDEX", "true").lower() == "true",
        )
    else:
        backend = InMemoryOpenSearchBackend(chunks, embedder=embedder)
    cache = SemanticCache(embedder=embedder, enabled=enable_cache)
    service = RagService(
        chunks=chunks,
        backend=backend,
        embedder=embedder,
        cache=cache,
        embedding_model_version=embedding_model_version,
        reranker=reranker,
        answer_composer=answer_composer,
        generation_model_version=generation_model_version,
    )
    users = load_users(users_path) if users_path else {}
    return service, users


def _env_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() == "true"


def _build_embedder_from_env() -> tuple[Any, str]:
    if not _env_true("BEDROCK_EMBEDDINGS_ENABLED"):
        embedder = EmbeddingModel()
        return embedder, embedder.name
    from .bedrock import BedrockEmbeddingModel

    embedder = BedrockEmbeddingModel()
    return embedder, embedder.model_id


def _build_reranker_from_env() -> Any | None:
    if not _env_true("BEDROCK_RERANK_ENABLED"):
        return None
    from .bedrock import BedrockReranker

    return BedrockReranker()


def _build_answer_composer_from_env() -> tuple[Any | None, str]:
    if not _env_true("BEDROCK_GENERATION_ENABLED"):
        return None, "deterministic-extractive-v1"
    from .bedrock import BedrockCitationGenerator

    generator = BedrockCitationGenerator()
    return (lambda query, context: generator.compose(query, context)), generator.model_id


def _citation_to_dict(citation: Any) -> dict[str, str]:
    return {
        "chunk_id": citation.chunk_id,
        "document_id": citation.document_id,
        "document_name": citation.document_name,
        "article": citation.article,
        "paragraph": citation.paragraph,
    }
