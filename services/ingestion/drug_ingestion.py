"""
Indian drug data ingestion into Qdrant.

Two data sources:
  1. Indian Medicine Dataset (github.com/junioralive/Indian-Medicine-Dataset)
     - 253,973 medicines with brand name, price, manufacturer
     - `short_composition1` / `short_composition2` → brand→generic mapping
  2. CDSCO Approved Drug List (Central Drugs Standard Control Organisation)
     - Official regulatory data: approved drugs, indications, approval dates
     - Scraped from cdsco.gov.in or ingested from bulk downloads

Stored in a SEPARATE Qdrant collection: `indian_drugs`
(separate from medical_evidence to allow targeted drug_lookup queries)

The brand→generic lookup table from this dataset is also used to seed
query_understanding.py's BRAND_TO_GENERIC dict.
"""

from __future__ import annotations

import csv
import json
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    HnswConfigDiff,
    PayloadSchemaType,
    PointStruct,
    SparseIndexParams,
    SparseVectorParams,
    SparseVector,
    VectorParams,
)

from shared.config import get_settings
from .embedder import BGEEmbedder

logger = logging.getLogger(__name__)
settings = get_settings()

_DENSE_VECTOR_NAME = "bge-m3-dense"
_SPARSE_VECTOR_NAME = "bge-m3-sparse"

# Expected CSV columns from Indian Medicine Dataset
_REQUIRED_COLS = {"name", "short_composition1"}


class DrugIngestion:
    def __init__(self) -> None:
        self._client = AsyncQdrantClient(
            url=settings.qdrant_url, api_key=settings.qdrant_api_key
        )
        self._embedder = BGEEmbedder()

    async def ingest_from_csv(self, csv_path: Path) -> None:
        """
        Ingest Indian Medicine Dataset CSV into the `indian_drugs` Qdrant collection.

        Download the dataset from:
          github.com/junioralive/Indian-Medicine-Dataset
          File: Medicine_Details.csv (or A_Z_medicines_dataset_of_India.csv)
        """
        if not csv_path.exists():
            raise FileNotFoundError(
                f"Dataset not found at {csv_path}. "
                "Download from github.com/junioralive/Indian-Medicine-Dataset"
            )

        await self._ensure_drug_collection()

        medicines = _parse_csv(csv_path)
        logger.info("Parsed %d medicines from CSV", len(medicines))

        batch_size = 64
        for i in range(0, len(medicines), batch_size):
            batch = medicines[i : i + batch_size]
            texts = [_medicine_to_text(m) for m in batch]
            dense_vecs, sparse_vecs = await self._embedder.embed_batch(texts)

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        _DENSE_VECTOR_NAME: dense,
                        _SPARSE_VECTOR_NAME: SparseVector(
                            indices=list(sparse.keys()),
                            values=list(sparse.values()),
                        ),
                    },
                    payload={
                        "text": text,
                        "brand_name": m.get("name", ""),
                        "generic_name": m.get("short_composition1", ""),
                        "generic_name2": m.get("short_composition2", ""),
                        "manufacturer": m.get("manufacturer_name", ""),
                        "price": m.get("price", ""),
                        "pack_size": m.get("pack_size_label", ""),
                        "source": "IndianMedicineDataset",
                        "tier": 7,
                        "doc_type": "drug",
                    },
                )
                for m, text, dense, sparse in zip(batch, texts, dense_vecs, sparse_vecs)
            ]

            await self._client.upsert(
                collection_name=settings.qdrant_collection_drugs,
                points=points,
                wait=True,
            )
            logger.info("Upserted drugs batch %d/%d", i // batch_size + 1, -(-len(medicines) // batch_size))

        logger.info("Drug ingestion complete: %d medicines indexed", len(medicines))

    async def export_brand_generic_map(self) -> dict[str, str]:
        """
        Export brand→generic mappings for use in query_understanding.py.
        Returns dict: {brand_name_lower: generic_name}
        """
        # Scroll through all drug records to build the lookup table
        brand_map: dict[str, str] = {}
        offset = None

        while True:
            result, offset = await self._client.scroll(
                collection_name=settings.qdrant_collection_drugs,
                scroll_filter=None,
                limit=1000,
                offset=offset,
                with_payload=True,
            )
            for point in result:
                brand = point.payload.get("brand_name", "")
                generic = point.payload.get("generic_name", "")
                if brand and generic:
                    brand_map[brand.lower()] = generic
            if offset is None:
                break

        logger.info("Exported %d brand→generic mappings", len(brand_map))
        return brand_map

    async def ingest_cdsco(self, cdsco_path: Path | None = None) -> None:
        """
        Ingest CDSCO (Central Drugs Standard Control Organisation) approved drug list.

        Accepts a JSON file with structure:
        [{"drug_name": "...", "generic_name": "...", "category": "...",
          "approval_date": "...", "manufacturer": "...", "indication": "...",
          "formulation": "...", "schedule": "H/H1/X/OTC"}]

        If no file is provided, attempts to fetch from CDSCO's public data
        portal (cdsco.gov.in). Note: CDSCO does not have a stable API, so
        the bulk JSON approach is more reliable.
        """
        await self._ensure_drug_collection()

        if cdsco_path and cdsco_path.exists():
            drugs = _parse_cdsco_json(cdsco_path)
        else:
            drugs = await self._fetch_cdsco_from_portal()

        if not drugs:
            logger.warning("No CDSCO drugs to ingest")
            return

        logger.info("Ingesting %d CDSCO approved drugs", len(drugs))

        batch_size = 64
        for i in range(0, len(drugs), batch_size):
            batch = drugs[i : i + batch_size]
            texts = [_cdsco_drug_to_text(d) for d in batch]
            dense_vecs, sparse_vecs = await self._embedder.embed_batch(texts)

            points = [
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector={
                        _DENSE_VECTOR_NAME: dense,
                        _SPARSE_VECTOR_NAME: SparseVector(
                            indices=list(sparse.keys()),
                            values=list(sparse.values()),
                        ),
                    },
                    payload={
                        "text": text,
                        "brand_name": d.get("drug_name", ""),
                        "generic_name": d.get("generic_name", ""),
                        "manufacturer": d.get("manufacturer", ""),
                        "indication": d.get("indication", ""),
                        "formulation": d.get("formulation", ""),
                        "schedule": d.get("schedule", ""),
                        "approval_date": d.get("approval_date", ""),
                        "category": d.get("category", ""),
                        "source": "CDSCO",
                        "tier": 1,  # Official regulatory data = highest tier
                        "doc_type": "drug_regulatory",
                    },
                )
                for d, text, dense, sparse in zip(batch, texts, dense_vecs, sparse_vecs)
            ]

            await self._client.upsert(
                collection_name=settings.qdrant_collection_drugs,
                points=points,
                wait=True,
            )

        logger.info("CDSCO ingestion complete: %d drugs indexed", len(drugs))

    async def _fetch_cdsco_from_portal(self) -> list[dict[str, Any]]:
        """
        Attempt to fetch approved drugs from CDSCO data portal.
        Falls back gracefully if the portal is unavailable.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # CDSCO publishes approved new drugs lists as PDFs/Excel.
                # This endpoint checks for a structured JSON export if available.
                response = await client.get(
                    "https://cdsco.gov.in/opencms/resources/UploadCDSCOWeb/2018/UploadApprovedNewDrugs/approveddruglist.json",
                    follow_redirects=True,
                )
                if response.status_code == 200:
                    return response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            logger.info(
                "CDSCO portal fetch failed (expected — use local JSON file): %s", e
            )
        return []

    async def _ensure_drug_collection(self) -> None:
        exists = await self._client.collection_exists(settings.qdrant_collection_drugs)
        if exists:
            return

        await self._client.create_collection(
            collection_name=settings.qdrant_collection_drugs,
            vectors_config={
                _DENSE_VECTOR_NAME: VectorParams(
                    size=1024,
                    distance=Distance.COSINE,
                    hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
                )
            },
            sparse_vectors_config={
                _SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )
            },
        )

        for field_name, schema_type in [
            ("brand_name", PayloadSchemaType.KEYWORD),
            ("generic_name", PayloadSchemaType.KEYWORD),
            ("manufacturer", PayloadSchemaType.KEYWORD),
        ]:
            await self._client.create_payload_index(
                collection_name=settings.qdrant_collection_drugs,
                field_name=field_name,
                field_schema=schema_type,
            )

        logger.info("Created '%s' Qdrant collection.", settings.qdrant_collection_drugs)


def _parse_csv(csv_path: Path) -> list[dict[str, Any]]:
    medicines = []
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalize column names (dataset uses different casing)
            normalized = {k.lower().strip(): v.strip() for k, v in row.items()}
            # Map common column name variants
            if "medicine name" in normalized and "name" not in normalized:
                normalized["name"] = normalized.pop("medicine name")
            if normalized.get("name") and normalized.get("short_composition1"):
                medicines.append(normalized)
    return medicines


def _medicine_to_text(m: dict[str, Any]) -> str:
    """Build a searchable text representation for embedding."""
    parts = [m.get("name", "")]
    if m.get("short_composition1"):
        parts.append(f"Generic: {m['short_composition1']}")
    if m.get("short_composition2"):
        parts.append(m["short_composition2"])
    if m.get("manufacturer_name"):
        parts.append(f"Manufacturer: {m['manufacturer_name']}")
    return " | ".join(filter(None, parts))


def _parse_cdsco_json(path: Path) -> list[dict[str, Any]]:
    """Parse CDSCO approved drug list from JSON file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "drugs" in data:
        return data["drugs"]
    return []


def _cdsco_drug_to_text(d: dict[str, Any]) -> str:
    """Build searchable text for a CDSCO-approved drug."""
    parts = [d.get("drug_name", "")]
    if d.get("generic_name"):
        parts.append(f"Generic: {d['generic_name']}")
    if d.get("indication"):
        parts.append(f"Indication: {d['indication']}")
    if d.get("formulation"):
        parts.append(f"Form: {d['formulation']}")
    if d.get("schedule"):
        parts.append(f"Schedule: {d['schedule']}")
    if d.get("manufacturer"):
        parts.append(f"Manufacturer: {d['manufacturer']}")
    if d.get("approval_date"):
        parts.append(f"Approved: {d['approval_date']}")
    return " | ".join(filter(None, parts))
