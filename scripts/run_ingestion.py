"""
One-shot ingestion script for bootstrapping the Qdrant collection.

Runs:
  1. Collection creation with schema (idempotent)
  2. ICMR PDF ingestion from GCS
  3. PubMed abstract ingestion for key domains

Usage:
  python scripts/run_ingestion.py --source icmr
  python scripts/run_ingestion.py --source pubmed
  python scripts/run_ingestion.py --source all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def main(source: str) -> None:
    from services.ingestion.qdrant_writer import QdrantWriter
    from services.ingestion.icmr_parser import ICMRParser
    from services.ingestion.pubmed_fetcher import PubMedFetcher

    # Always ensure collection schema is in place
    writer = QdrantWriter()
    logger.info("Ensuring Qdrant collection exists…")
    await writer.ensure_collection()

    if source in ("icmr", "all"):
        logger.info("Starting ICMR ingestion…")
        parser = ICMRParser()
        await parser.ingest_all()
        logger.info("ICMR ingestion complete.")

    if source in ("pubmed", "all"):
        logger.info("Starting PubMed ingestion…")
        fetcher = PubMedFetcher()
        await fetcher.ingest_all_domains()
        logger.info("PubMed ingestion complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run Hunt AI data ingestion")
    parser.add_argument(
        "--source",
        choices=["icmr", "pubmed", "all"],
        default="all",
        help="Which data source to ingest",
    )
    args = parser.parse_args()
    asyncio.run(main(args.source))
