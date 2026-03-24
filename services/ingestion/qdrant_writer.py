"""
Qdrant collection management and chunk upsert.

Collection schema:
- Dense vector: bge-m3-dense (1024-dim, cosine, binary quantization)
- Sparse vector: bge-m3-sparse (SPLADE, IDF modifier)
- Payload indexes: tier, pub_year, source, doc_type, is_open_access
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    BinaryQuantizationConfig,
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    KeywordIndexParams,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    TextIndexParams,
    TokenizerType,
    VectorParams,
    SparseVector,
)

from shared.config import get_settings
from shared.utils import StructureAwareChunker
from shared.utils.chunker import DocumentChunk

logger = logging.getLogger(__name__)
settings = get_settings()

_DENSE_VECTOR_NAME = "bge-m3-dense"
_SPARSE_VECTOR_NAME = "bge-m3-sparse"


class QdrantWriter:
    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )

    async def ensure_collection(self) -> None:
        """Create collection if it doesn't exist. Safe to call repeatedly."""
        exists = await self._client.collection_exists(settings.qdrant_collection_guidelines)
        if exists:
            logger.info("Collection '%s' already exists.", settings.qdrant_collection_guidelines)
            return

        await self._client.create_collection(
            collection_name=settings.qdrant_collection_guidelines,
            vectors_config={
                _DENSE_VECTOR_NAME: VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
                    quantization_config=BinaryQuantizationConfig(always_ram=True),
                )
            },
            sparse_vectors_config={
                _SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )
            },
        )

        # Create payload indexes for fast metadata filtering
        payload_indexes: list[tuple[str, PayloadSchemaType]] = [
            ("tier", PayloadSchemaType.INTEGER),
            ("pub_year", PayloadSchemaType.INTEGER),
            ("source", PayloadSchemaType.KEYWORD),
            ("doc_type", PayloadSchemaType.KEYWORD),
            ("is_open_access", PayloadSchemaType.BOOL),
        ]
        for field_name, schema_type in payload_indexes:
            await self._client.create_payload_index(
                collection_name=settings.qdrant_collection_guidelines,
                field_name=field_name,
                field_schema=schema_type,
            )

        logger.info("Collection '%s' created with indexes.", settings.qdrant_collection_guidelines)

    async def upsert_chunks(
        self,
        chunks: list[DocumentChunk],
        dense_vecs: list[list[float]],
        sparse_vecs: list[dict[int, float]],
    ) -> None:
        """Upsert chunks in batches of 100 to avoid Qdrant request size limits."""
        points: list[PointStruct] = []

        for chunk, dense, sparse in zip(chunks, dense_vecs, sparse_vecs):
            point_id = str(uuid.uuid4())
            payload: dict[str, Any] = {
                "text": chunk.text,
                **chunk.metadata,
            }
            points.append(
                PointStruct(
                    id=point_id,
                    vector={
                        _DENSE_VECTOR_NAME: dense,
                        _SPARSE_VECTOR_NAME: SparseVector(
                            indices=list(sparse.keys()),
                            values=list(sparse.values()),
                        ),
                    },
                    payload=payload,
                )
            )

        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self._client.upsert(
                collection_name=settings.qdrant_collection_guidelines,
                points=batch,
                wait=True,
            )
            logger.debug("Upserted batch %d/%d", i // batch_size + 1, -(-len(points) // batch_size))
