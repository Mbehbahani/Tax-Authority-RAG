"""Conservative semantic cache backends.

The cache is authorization-scoped: the key hash includes role scope, clearance,
denied-classification tags, corpus version, embedding model version, and the set
of citation ids. Two users with different auth scopes can never share a cache
entry, even for identical queries.

The default backend is in-memory for fast deterministic tests. ``RedisSemanticCache``
uses the same public interface for the local real-stack profile.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Iterable

from .embeddings import EmbeddingModel, cosine_similarity
from .models import Citation, UserContext
from .security import AuthFilter, build_auth_filter


SAFE_THRESHOLD = 0.95
MIN_THRESHOLD = 0.92


@dataclass
class CachedEntry:
    key: str
    normalized_query: str
    answer_text: str
    citations: list[Citation]
    scope_hash: str
    corpus_version: str
    embedding_model_version: str
    citation_ids_hash: str
    query_embedding: list[float] = field(default_factory=list)


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


def _hash_citation_ids(citations: Iterable[Citation]) -> str:
    ids = sorted({c.chunk_id for c in citations})
    return hashlib.sha256("::".join(ids).encode("utf-8")).hexdigest()[:16]


def _build_cache_key(
    *,
    normalized_query: str,
    scope_hash: str,
    corpus_version: str,
    embedding_model_version: str,
    citation_ids_hash: str,
) -> str:
    raw = f"{normalized_query}|{scope_hash}|{corpus_version}|{embedding_model_version}|{citation_ids_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SemanticCache:
    def __init__(
        self,
        *,
        embedder: EmbeddingModel,
        safe_threshold: float = SAFE_THRESHOLD,
        min_threshold: float = MIN_THRESHOLD,
        enabled: bool = False,
    ) -> None:
        self._embedder = embedder
        self._safe_threshold = safe_threshold
        self._min_threshold = min_threshold
        self._enabled = enabled
        self._entries: list[CachedEntry] = []

    # -----------------------------------------------------------------

    def enable(self, enabled: bool = True) -> None:
        self._enabled = enabled

    @property
    def entries(self) -> list[CachedEntry]:
        return list(self._entries)

    # -----------------------------------------------------------------

    def lookup(
        self,
        query: str,
        user: UserContext,
        *,
        corpus_version: str,
        embedding_model_version: str,
        auth: AuthFilter | None = None,
    ) -> CachedEntry | None:
        if not self._enabled:
            return None
        auth = auth or build_auth_filter(user)
        normalized = _normalize_query(query)
        query_emb = self._embedder.embed(query)
        scope_hash = auth.scope_hash()

        candidates: list[tuple[CachedEntry, float]] = []
        for entry in self._entries:
            if entry.scope_hash != scope_hash:
                # Role/clearance/denied-tag scope must match exactly.
                continue
            if entry.corpus_version != corpus_version:
                continue
            if entry.embedding_model_version != embedding_model_version:
                continue
            sim = cosine_similarity(query_emb, entry.query_embedding)
            if sim >= self._safe_threshold:
                candidates.append((entry, sim))
        if not candidates:
            return None
        candidates.sort(key=lambda row: row[1], reverse=True)
        return candidates[0][0]

    # -----------------------------------------------------------------

    def write(
        self,
        query: str,
        user: UserContext,
        answer_text: str,
        citations: list[Citation],
        *,
        corpus_version: str,
        embedding_model_version: str,
        auth: AuthFilter | None = None,
        is_cache_safe: bool,
    ) -> CachedEntry | None:
        if not self._enabled:
            return None
        if not is_cache_safe:
            return None
        if not citations:
            return None  # Never cache uncited answers.
        for cite in citations:
            if not cite.is_complete():
                return None

        auth = auth or build_auth_filter(user)
        normalized = _normalize_query(query)
        query_emb = self._embedder.embed(query)
        scope_hash = auth.scope_hash()
        citation_ids_hash = _hash_citation_ids(citations)
        key = _build_cache_key(
            normalized_query=normalized,
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
            citation_ids_hash=citation_ids_hash,
        )
        entry = CachedEntry(
            key=key,
            normalized_query=normalized,
            answer_text=answer_text,
            citations=list(citations),
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
            citation_ids_hash=citation_ids_hash,
            query_embedding=query_emb,
        )
        self._entries.append(entry)
        return entry

    def clear(self) -> None:
        self._entries.clear()


class RedisSemanticCache:
    """Redis-backed semantic cache with the same contract as ``SemanticCache``.

    The implementation intentionally scans only the current authorization/model
    namespace during lookup. That keeps cache reuse scoped by RBAC, corpus
    version, and embedding model version before any semantic similarity check is
    attempted.
    """

    def __init__(
        self,
        *,
        embedder: EmbeddingModel,
        redis_url: str,
        safe_threshold: float = SAFE_THRESHOLD,
        min_threshold: float = MIN_THRESHOLD,
        ttl_seconds: int = 3600,
        enabled: bool = False,
        key_prefix: str = "taxrag:semantic-cache",
    ) -> None:
        try:
            import redis
        except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("redis package is required for RedisSemanticCache") from exc

        self._embedder = embedder
        self._safe_threshold = safe_threshold
        self._min_threshold = min_threshold
        self._ttl_seconds = ttl_seconds
        self._enabled = enabled
        self._key_prefix = key_prefix.rstrip(":")
        self._client = redis.Redis.from_url(redis_url, decode_responses=True)

    # -----------------------------------------------------------------

    def enable(self, enabled: bool = True) -> None:
        self._enabled = enabled

    @property
    def entries(self) -> list[CachedEntry]:
        return [entry for entry in self._iter_entries(f"{self._key_prefix}:*")]

    # -----------------------------------------------------------------

    def lookup(
        self,
        query: str,
        user: UserContext,
        *,
        corpus_version: str,
        embedding_model_version: str,
        auth: AuthFilter | None = None,
    ) -> CachedEntry | None:
        if not self._enabled:
            return None
        auth = auth or build_auth_filter(user)
        query_emb = self._embedder.embed(query)
        scope_hash = auth.scope_hash()
        namespace = self._namespace(
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
        )

        candidates: list[tuple[CachedEntry, float]] = []
        for entry in self._iter_entries(f"{namespace}:*"):
            sim = cosine_similarity(query_emb, entry.query_embedding)
            if sim >= self._safe_threshold:
                candidates.append((entry, sim))
        if not candidates:
            return None
        candidates.sort(key=lambda row: row[1], reverse=True)
        return candidates[0][0]

    # -----------------------------------------------------------------

    def write(
        self,
        query: str,
        user: UserContext,
        answer_text: str,
        citations: list[Citation],
        *,
        corpus_version: str,
        embedding_model_version: str,
        auth: AuthFilter | None = None,
        is_cache_safe: bool,
    ) -> CachedEntry | None:
        if not self._enabled:
            return None
        if not is_cache_safe or not citations:
            return None
        if any(not cite.is_complete() for cite in citations):
            return None

        auth = auth or build_auth_filter(user)
        normalized = _normalize_query(query)
        query_emb = self._embedder.embed(query)
        scope_hash = auth.scope_hash()
        citation_ids_hash = _hash_citation_ids(citations)
        local_key = _build_cache_key(
            normalized_query=normalized,
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
            citation_ids_hash=citation_ids_hash,
        )
        namespace = self._namespace(
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
        )
        redis_key = f"{namespace}:{local_key}"
        entry = CachedEntry(
            key=redis_key,
            normalized_query=normalized,
            answer_text=answer_text,
            citations=list(citations),
            scope_hash=scope_hash,
            corpus_version=corpus_version,
            embedding_model_version=embedding_model_version,
            citation_ids_hash=citation_ids_hash,
            query_embedding=query_emb,
        )
        self._client.set(redis_key, json.dumps(_entry_to_json(entry)), ex=self._ttl_seconds)
        return entry

    def clear(self) -> None:
        keys = list(self._client.scan_iter(f"{self._key_prefix}:*"))
        if keys:
            self._client.delete(*keys)

    def _namespace(self, *, scope_hash: str, corpus_version: str, embedding_model_version: str) -> str:
        return f"{self._key_prefix}:{scope_hash}:{corpus_version}:{embedding_model_version}"

    def _iter_entries(self, pattern: str) -> Iterable[CachedEntry]:
        for key in self._client.scan_iter(pattern):
            raw = self._client.get(key)
            if not raw:
                continue
            try:
                yield _entry_from_json(json.loads(raw), key=key)
            except Exception:
                continue


def _entry_to_json(entry: CachedEntry) -> dict[str, object]:
    return {
        "key": entry.key,
        "normalized_query": entry.normalized_query,
        "answer_text": entry.answer_text,
        "citations": [citation.__dict__ for citation in entry.citations],
        "scope_hash": entry.scope_hash,
        "corpus_version": entry.corpus_version,
        "embedding_model_version": entry.embedding_model_version,
        "citation_ids_hash": entry.citation_ids_hash,
        "query_embedding": entry.query_embedding,
        "created_at": time.time(),
    }


def _entry_from_json(data: dict[str, object], *, key: str) -> CachedEntry:
    return CachedEntry(
        key=key,
        normalized_query=str(data.get("normalized_query", "")),
        answer_text=str(data.get("answer_text", "")),
        citations=[Citation(**item) for item in data.get("citations", [])],  # type: ignore[arg-type]
        scope_hash=str(data.get("scope_hash", "")),
        corpus_version=str(data.get("corpus_version", "")),
        embedding_model_version=str(data.get("embedding_model_version", "")),
        citation_ids_hash=str(data.get("citation_ids_hash", "")),
        query_embedding=[float(v) for v in data.get("query_embedding", [])],  # type: ignore[union-attr]
    )
