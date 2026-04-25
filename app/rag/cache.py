"""Conservative in-memory semantic cache.

The cache is authorization-scoped: the key hash includes role scope, clearance,
denied-classification tags, corpus version, embedding model version, and the
set of citation ids. Two users with different auth scopes can never share a
cache entry, even for identical queries.

Swap this module for a Redis-backed implementation later by keeping the same
public interface (``lookup``, ``write``).
"""

from __future__ import annotations

import hashlib
import json
import re
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
