"""
Migrate existing ICMR embeddings from Firestore → Qdrant Cloud.

Context (from blueprint):
  The ICMR PDFs were already batch-processed and stored in:
  - Firestore collection: guideline_chunks (fields: content, embedding_vector, created_at)
  - GCS: raw-indian-medical-guidelines-pdfs-processed-batch/ (JSON outputs)

Why migrate? Firestore does not support hybrid search (dense + sparse vectors).
Qdrant Cloud enables BGE-M3 hybrid search for dramatically better retrieval.

Migration strategy:
  1. Read all documents from Firestore guideline_chunks
  2. Re-embed each chunk with BGE-M3 (generates dense + sparse in one pass)
     (The existing embedding_vector field used a different model — must regenerate)
  3. Upload to Qdrant medical_evidence collection with full metadata
  4. Validate search quality against 5-query test set

Usage:
  python scripts/migrate_firestore_to_qdrant.py [--dry-run]
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_BATCH_SIZE = 50  # Firestore + Qdrant batch size


async def migrate(dry_run: bool = False) -> None:
    from google.cloud import firestore
    from shared.config import get_settings
    from shared.utils.chunker import DocumentChunk
    from services.ingestion.embedder import BGEEmbedder
    from services.ingestion.qdrant_writer import QdrantWriter

    settings = get_settings()
    db = firestore.AsyncClient(project=settings.gcp_project_id)
    embedder = BGEEmbedder()
    writer = QdrantWriter()

    if not dry_run:
        logger.info("Ensuring Qdrant collection exists…")
        await writer.ensure_collection()

    # Stream all docs from Firestore
    collection_ref = db.collection(settings.firestore_collection_chunks)
    docs = collection_ref.stream()

    batch_texts: list[str] = []
    batch_metas: list[dict] = []
    total_migrated = 0

    async for doc in docs:
        data = doc.to_dict()
        content = data.get("content", "").strip()
        if not content:
            continue

        # Reconstruct metadata from Firestore fields
        meta = {
            "source": "ICMR_STW",
            "doc_type": "guideline",
            "tier": 1,
            "is_landmark": False,
            "is_open_access": True,
            "firestore_id": doc.id,
            # Preserve any extra fields stored in Firestore
            **{k: v for k, v in data.items() if k not in ("content", "embedding_vector")},
        }
        # Ensure required fields
        meta.setdefault("year", 2023)
        meta.setdefault("pub_year", meta["year"])

        batch_texts.append(content)
        batch_metas.append(meta)

        if len(batch_texts) >= _BATCH_SIZE:
            await _flush_batch(batch_texts, batch_metas, embedder, writer, dry_run)
            total_migrated += len(batch_texts)
            logger.info("Migrated %d chunks so far…", total_migrated)
            batch_texts.clear()
            batch_metas.clear()

    # Flush remaining
    if batch_texts:
        await _flush_batch(batch_texts, batch_metas, embedder, writer, dry_run)
        total_migrated += len(batch_texts)

    logger.info("Migration complete: %d chunks migrated", total_migrated)

    # Quick validation
    logger.info("Running validation queries…")
    await _validate_search()


async def _flush_batch(
    texts: list[str],
    metas: list[dict],
    embedder: "BGEEmbedder",
    writer: "QdrantWriter",
    dry_run: bool,
) -> None:
    from shared.utils.chunker import DocumentChunk

    dense_vecs, sparse_vecs = await embedder.embed_batch(texts)
    chunks = [
        DocumentChunk(text=t, metadata=m, token_count=len(t) // 4)
        for t, m in zip(texts, metas)
    ]

    if dry_run:
        logger.info("[DRY RUN] Would upsert %d chunks", len(chunks))
        return

    await writer.upsert_chunks(chunks, dense_vecs, sparse_vecs)


async def _validate_search() -> None:
    """Spot-check retrieval quality with known ICMR queries."""
    from qdrant_client import AsyncQdrantClient
    from shared.config import get_settings

    settings = get_settings()
    client = AsyncQdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)

    test_queries = [
        "tuberculosis first-line treatment ICMR",
        "malaria artemisinin India",
        "type 2 diabetes metformin guidelines",
    ]

    from services.ingestion.embedder import BGEEmbedder
    embedder = BGEEmbedder()

    for query in test_queries:
        dense, _ = await embedder.embed_batch([query])
        results = await client.search(
            collection_name=settings.qdrant_collection_guidelines,
            query_vector=("bge-m3-dense", dense[0]),
            limit=3,
        )
        logger.info(
            "Query: '%s' → top result: %s",
            query,
            results[0].payload.get("content", "")[:80] if results else "NO RESULTS",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Firestore ICMR chunks to Qdrant")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to Qdrant")
    args = parser.parse_args()
    asyncio.run(migrate(dry_run=args.dry_run))
