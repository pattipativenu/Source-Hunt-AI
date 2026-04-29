"""
Google Vertex AI text-embedding-004 embedder (alternative to BGE-M3).

Advantages over BGE-M3:
  - No GPU needed — pure Vertex AI API call
  - Matryoshka truncation: request 256/512/768 dims to cut storage cost
  - gemini-embedding-exp-03-07 (latest experimental) achieves MTEB 68.32
  - Zero cold-start on Cloud Run (no 500MB model to load)

Disadvantage:
  - No sparse vector output → dense-only search (lose BM25 keyword matching)

Auth: Application Default Credentials (ADC) — same as generation.
Usage: Switch EMBEDDING_BACKEND=google in .env to use this instead of BGE-M3.
"""

from __future__ import annotations

import asyncio
import logging

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_MODELS = {
    "text-embedding-004": 768,           # Stable, production-grade
    "gemini-embedding-exp-03-07": 3072,  # Experimental, highest quality
}

_DEFAULT_MODEL = "text-embedding-004"
_DEFAULT_DIM = 768  # Matryoshka: can be 256, 512, or 768

# Vertex AI accepts up to 250 texts per batch for text-embedding-004
_VERTEX_BATCH_SIZE = 250


class GoogleEmbedder:
    """Async wrapper around Vertex AI text embedding API using ADC."""

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        output_dimensionality: int = _DEFAULT_DIM,
    ) -> None:
        self._model_name = model
        self._dim = output_dimensionality
        self._vertex_model: object | None = None  # lazy-loaded

    def _load(self) -> None:
        if self._vertex_model is not None:
            return
        try:
            import vertexai
            from vertexai.language_models import TextEmbeddingModel  # type: ignore[import]
        except ImportError as e:
            raise RuntimeError(
                "Run: pip install google-cloud-aiplatform\n"
                "Local auth: gcloud auth application-default login"
            ) from e

        vertexai.init(project=settings.gcp_project_id, location=settings.gcp_region)
        self._vertex_model = TextEmbeddingModel.from_pretrained(self._model_name)
        logger.info("Vertex TextEmbeddingModel loaded: %s", self._model_name)

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
        from vertexai.language_models import TextEmbeddingInput  # type: ignore[import]
        assert self._vertex_model is not None
        results: list[list[float]] = []

        for i in range(0, len(texts), _VERTEX_BATCH_SIZE):
            batch = texts[i : i + _VERTEX_BATCH_SIZE]
            inputs = [TextEmbeddingInput(text, task_type) for text in batch]
            embeddings = self._vertex_model.get_embeddings(  # type: ignore[attr-defined]
                inputs, output_dimensionality=self._dim
            )
            results.extend(e.values for e in embeddings)

        return results
