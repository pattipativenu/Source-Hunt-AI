"""
Async token-bucket rate limiter for NCBI E-utilities (max 10 req/s with API key).
Uses asyncio primitives — no external dependencies.
"""

from __future__ import annotations

import asyncio
import time


class AsyncTokenBucketLimiter:
    """
    Token-bucket rate limiter safe for concurrent asyncio tasks.

    Usage:
        limiter = AsyncTokenBucketLimiter(rate=10, capacity=10)
        async with limiter:
            response = await client.get(url)
    """

    def __init__(self, rate: float, capacity: float) -> None:
        self._rate = rate          # tokens added per second
        self._capacity = capacity  # max burst
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def _acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self._capacity,
                self._tokens + elapsed * self._rate,
            )
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1

    async def __aenter__(self) -> "AsyncTokenBucketLimiter":
        await self._acquire()
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
