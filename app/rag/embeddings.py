"""Deterministic, dependency-free embedding for local tests.

Not a replacement for Cohere Embed v4 / Titan; the goal is to give the local
PoC a stable, reproducible vector space so retrieval/RRF/grader logic can be
validated offline. The interface mirrors a batch embedding API so the Bedrock
adapter can drop in later without changing callers.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass

DEFAULT_DIM = 128
_TOKEN_RE = re.compile(r"[A-Za-z0-9\.\-:_]+")


@dataclass(frozen=True)
class EmbeddingModel:
    name: str = "local-deterministic-v1"
    dimension: int = DEFAULT_DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        tokens = _tokenize(text)
        if not tokens:
            return vec
        for tok in tokens:
            h = hashlib.blake2b(tok.lower().encode("utf-8"), digest_size=8).digest()
            for i, byte in enumerate(h):
                idx = (i * 16 + byte) % self.dimension
                sign = 1.0 if (byte & 1) == 0 else -1.0
                vec[idx] += sign * 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            return vec
        return [v / norm for v in vec]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    # vectors are unit-norm by construction, clamp for safety
    return max(-1.0, min(1.0, dot))


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)
