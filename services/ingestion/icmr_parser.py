"""
ICMR PDF ingestion pipeline (Tier 1 — highest priority).

Flow:
  GCS bucket → download PDF bytes → Marker (primary) or PyMuPDF4LLM (fallback)
  → markdown → StructureAwareChunker → BGE-M3 embeddings → Qdrant upsert

Marker is preferred because:
- Faster batch throughput on GCP Cloud Run Jobs
- Better table preservation for dosage charts
- Handles mixed scanned + digital PDFs in the ICMR corpus

PyMuPDF4LLM fallback for when Marker is unavailable:
- Lighter install (no ML models needed), faster cold-start
- Good for pure-digital PDFs (most ICMR STW volumes)
- Uses PyMuPDF's native text extraction → markdown conversion
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any

from google.cloud import storage
from qdrant_client import AsyncQdrantClient

from shared.config import get_settings
from shared.utils import StructureAwareChunker
from .embedder import BGEEmbedder
from .qdrant_writer import QdrantWriter

logger = logging.getLogger(__name__)

settings = get_settings()


class ICMRParser:
    def __init__(self) -> None:
        self._gcs = storage.Client()
        self._chunker = StructureAwareChunker()
        self._embedder = BGEEmbedder()
        self._qdrant = QdrantWriter()

    async def ingest_all(self) -> None:
        """Download and ingest every PDF in the ICMR GCS bucket."""
        bucket = self._gcs.bucket(settings.gcs_bucket_icmr)
        blobs = list(bucket.list_blobs())
        pdf_blobs = [b for b in blobs if b.name.lower().endswith(".pdf")]
        logger.info("Found %d ICMR PDFs to ingest", len(pdf_blobs))

        for blob in pdf_blobs:
            await self._ingest_single(blob)

    async def _ingest_single(self, blob: storage.Blob) -> None:
        logger.info("Ingesting: %s", blob.name)
        pdf_bytes = blob.download_as_bytes()
        markdown = _parse_with_marker(pdf_bytes, blob.name)

        # Extract volume/year from blob path convention: ICMR_STW_Vol2_2023.pdf
        base_meta = _extract_blob_metadata(blob.name)

        chunks = self._chunker.chunk_document(markdown, base_meta)
        logger.info("  → %d chunks from %s", len(chunks), blob.name)

        dense_vecs, sparse_vecs = await self._embedder.embed_batch(
            [c.text for c in chunks]
        )

        await self._qdrant.upsert_chunks(chunks, dense_vecs, sparse_vecs)
        logger.info("  ✓ Upserted %d chunks for %s", len(chunks), blob.name)


def _parse_with_marker(pdf_bytes: bytes, filename: str) -> str:
    """
    Parse PDF bytes with Marker (primary) or PyMuPDF4LLM (fallback).
    Both are imported at call-time to avoid loading heavy ML models at module
    import (important for Cloud Run cold-start latency).
    """
    tmp = Path(f"/tmp/{Path(filename).name}")
    tmp.write_bytes(pdf_bytes)

    # Try Marker first (better table handling, OCR for scanned pages)
    try:
        from marker.converters.pdf import PdfConverter  # type: ignore[import]
        from marker.models import create_model_dict       # type: ignore[import]
        from marker.output import text_from_rendered      # type: ignore[import]

        models = create_model_dict()
        converter = PdfConverter(artifact_dict=models)
        rendered = converter(str(tmp))
        markdown, _, _ = text_from_rendered(rendered)
        tmp.unlink(missing_ok=True)
        return markdown
    except ImportError:
        logger.info("Marker not available, falling back to PyMuPDF4LLM for %s", filename)
    except Exception as e:
        logger.warning("Marker failed for %s: %s — trying PyMuPDF4LLM", filename, e)

    # Fallback: PyMuPDF4LLM (lighter, no ML models, works for digital PDFs)
    try:
        import pymupdf4llm  # type: ignore[import]

        markdown = pymupdf4llm.to_markdown(str(tmp))
        tmp.unlink(missing_ok=True)
        return markdown
    except ImportError:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            "Neither marker-pdf nor pymupdf4llm is installed. "
            "Run: pip install marker-pdf  OR  pip install pymupdf4llm"
        )


def _extract_blob_metadata(blob_name: str) -> dict[str, Any]:
    """
    Derive structured metadata from GCS object path.
    Expected convention: ICMR_STW_VolN_YYYY.pdf  (case-insensitive)
    Falls back gracefully for non-conforming names.
    """
    stem = Path(blob_name).stem.upper()
    parts = stem.split("_")

    volume = None
    year = None
    for part in parts:
        if part.startswith("VOL"):
            volume = part.replace("VOL", "Volume ")
        if len(part) == 4 and part.isdigit():
            year = int(part)

    return {
        "source": "ICMR_STW",
        "doc_type": "guideline",
        "tier": 1,
        "volume": volume or blob_name,
        "year": year or 2023,
        "is_landmark": False,
        "is_open_access": True,
    }
