"""
Redis cache wrapper for:
- Semantic query cache (embedding cosine similarity ≥ 0.98)
- DOI validation cache (24h TTL)
- Full response cache (12h TTL)
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import redis.asyncio as aioredis


class RedisCache:
    def __init__(self, host: str, port: int) -> None:
        self._client: aioredis.Redis = aioredis.Redis(host=host, port=port, decode_responses=True)

    # ── Response cache ────────────────────────────────────────────────────────

    async def get_response(self, query: str) -> dict[str, Any] | None:
        key = f"response:{_sha256(query)}"
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def set_response(self, query: str, response: dict[str, Any], ttl: int) -> None:
        key = f"response:{_sha256(query)}"
        await self._client.setex(key, ttl, json.dumps(response))

    # ── DOI cache ────────────────────────────────────────────────────────────

    async def get_doi(self, doi: str) -> dict[str, Any] | None:
        key = f"doi:{doi}"
        raw = await self._client.get(key)
        return json.loads(raw) if raw else None

    async def set_doi(self, doi: str, metadata: dict[str, Any], ttl: int) -> None:
        key = f"doi:{doi}"
        await self._client.setex(key, ttl, json.dumps(metadata))

    # ── Semantic cache (embedding-based) ─────────────────────────────────────

    async def store_embedding(self, query: str, embedding: list[float], response: dict[str, Any], ttl: int) -> None:
        """Store query embedding + response for semantic cache lookup."""
        key = f"semcache:{_sha256(query)}"
        payload = {"embedding": embedding, "response": response}
        await self._client.setex(key, ttl, json.dumps(payload))

    async def find_semantic_match(
        self, query_embedding: list[float], candidate_keys: list[str], threshold: float = 0.98
    ) -> dict[str, Any] | None:
        """
        Brute-force cosine similarity over candidate keys.
        For production, replace with Redis Vector Search (RediSearch) or
        a dedicated vector index.
        """
        for key in candidate_keys:
            raw = await self._client.get(key)
            if not raw:
                continue
            payload = json.loads(raw)
            cached_emb = payload["embedding"]
            if _cosine_similarity(query_embedding, cached_emb) >= threshold:
                return payload["response"]
        return None

    async def close(self) -> None:
        await self._client.aclose()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
