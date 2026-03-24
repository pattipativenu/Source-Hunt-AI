"""
Google text-embedding-004 embedder (alternative to BGE-M3).

Advantages over BGE-M3:
  - No GPU needed — pure API call
  - Matryoshka truncation: request 256/512/768 dims to cut storage cost
  - Gemini-embedding-exp-03-07 (latest experimental) achieves MTEB 68.32
  - Zero cold-start on Cloud Run (no 500MB model to load)

Disadvantage:
  - No sparse vector output → dense-only search (lose BM25 keyword matching)
  - Cost: $0.00002/1K chars (effectively free at our scale)

Usage:
  Switch EMBEDDING_BACKEND=google in .env to use this instead of BGE-M3.
  The dashboard lets you A/B test retrieval quality between backends.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Latest Google embedding models (update as newer versions launch)
_MODELS = {
    "text-embedding-004": 768,           # Stable, production-grade
    "gemini-embedding-exp-03-07": 3072,  # Experimental, highest quality
}

_DEFAULT_MODEL = "text-embedding-004"
_DEFAULT_DIM = 768  # Matryoshka: can be 256, 512, or 768


class GoogleEmbedder:
    """
    Async wrapper around Google Generative AI text embedding API.
    Uses GEMINI_API_KEY from settings (same key as generation).
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        output_dimensionality: int = _DEFAULT_DIM,
    ) -> None:
        self._model = model
        self._dim = output_dimensionality
        self._client: Any = None  # lazy-loaded

    def _load(self) -> None:
        if self._client is not None:
            return
        try:
            import google.generativeai as genai  # type: ignore[import]
        except ImportError as e:
            raise RuntimeError("Run: pip install google-generativeai") from e

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        genai.configure(api_key=settings.gemini_api_key)
        self._client = genai

    async def embed_batch(
        self, texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
    ) -> list[list[float]]:
        """
        Embed a batch of texts. Returns dense vectors only (no sparse).
        task_type options: RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY
        """
        self._load()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts, task_type)

    async def embed_query(self, text: str) -> list[float]:
        """Embed a single query with the RETRIEVAL_QUERY task type."""
        vectors = await self.embed_batch([text], task_type="RETRIEVAL_QUERY")
        return vectors[0]

    def _embed_sync(self, texts: list[str], task_type: str) -> list[list[float]]:
        assert self._client is not None
        results: list[list[float]] = []

        # Google API accepts up to 100 texts per batch
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            response = self._client.embed_content(
                model=f"models/{self._model}",
                content=batch,
                task_type=task_type,
                output_dimensionality=self._dim,
            )
            # Response structure: {"embedding": [...]} for single, list for batch
            embeddings = response.get("embedding", [])
            if isinstance(embeddings[0], float):
                # Single item response
                results.append(embeddings)
            else:
                results.extend(embeddings)

        return results
