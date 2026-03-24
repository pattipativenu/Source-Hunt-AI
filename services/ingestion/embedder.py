"""
BGE-M3 embedding wrapper.

BGE-M3 generates dense (1024-dim) and sparse (SPLADE-style) vectors
in a single forward pass, making it the most efficient choice for
Qdrant hybrid search without running two separate models.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Batch size tuned for Cloud Run 4GB RAM instance
_BATCH_SIZE = 32


class BGEEmbedder:
    def __init__(self) -> None:
        self._model: Any | None = None  # lazy-loaded on first call

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            from FlagEmbedding import BGEM3FlagModel  # type: ignore[import]
        except ImportError as e:
            raise RuntimeError(
                "FlagEmbedding not installed. Run: pip install FlagEmbedding"
            ) from e
        logger.info("Loading BAAI/bge-m3 model (first call)…")
        self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
        logger.info("BGE-M3 loaded.")

    async def embed_batch(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict[int, float]]]:
        """
        Returns (dense_vectors, sparse_vectors).
        Each dense vector: list[float] of length 1024.
        Each sparse vector: dict mapping token_id → weight (SPLADE format).
        Runs CPU-bound model inference in a thread pool to stay async-friendly.
        """
        self._load()
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._embed_sync, texts)

    def _embed_sync(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict[int, float]]]:
        assert self._model is not None
        all_dense: list[list[float]] = []
        all_sparse: list[dict[int, float]] = []

        for i in range(0, len(texts), _BATCH_SIZE):
            batch = texts[i : i + _BATCH_SIZE]
            output = self._model.encode(
                batch,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            all_dense.extend(output["dense_vecs"].tolist())
            # Sparse output format: list of {token_id: weight}
            all_sparse.extend(output["lexical_weights"])

        return all_dense, all_sparse
