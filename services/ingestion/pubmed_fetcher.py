"""
PubMed / PMC ingestion via NCBI E-utilities.

Rate limit: 10 req/s with NCBI API key (3 req/s without).
Implements token-bucket rate limiting + tenacity exponential backoff.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from shared.config import get_settings
from shared.utils import AsyncTokenBucketLimiter
from .embedder import BGEEmbedder
from .qdrant_writer import QdrantWriter

logger = logging.getLogger(__name__)
settings = get_settings()

_NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_DOMAINS = [
    "cardiology[MeSH Major Topic]",
    "oncology[MeSH Major Topic]",
    "infectious disease[MeSH Major Topic]",
    "diabetes mellitus[MeSH Major Topic]",
    "nephrology[MeSH Major Topic]",
    "tuberculosis[MeSH Major Topic]",
    "malaria[MeSH Major Topic]",
    "dengue[MeSH Major Topic]",
]

# ── Journal tier mapping (from Hunt AI Medical Knowledge Graph Part 2) ────────
# Big 4 general medical journals (Tier 3) — highest impact, all specialties
_BIG4_JOURNALS = {
    "The New England journal of medicine", "N Engl J Med",
    "Lancet (London, England)", "Lancet", "The Lancet",
    "JAMA", "JAMA : the journal of the American Medical Association",
    "BMJ (Clinical research ed.)", "BMJ",
    "Nature medicine", "Nature Medicine",
}
# Tier 3 additional: top general journals
_TIER3_JOURNALS = _BIG4_JOURNALS | {
    "Annals of internal medicine", "JAMA internal medicine",
    "PLOS medicine", "The Cochrane database of systematic reviews",
}
# Specialty parent journals (Tier 4 — high-impact within specialty)
_SPECIALTY_PARENT_JOURNALS = {
    "Circulation", "Journal of the American College of Cardiology",
    "European heart journal", "Journal of clinical oncology",
    "The Lancet. Oncology", "Annals of oncology",
    "Gastroenterology", "Gut", "Hepatology",
    "Diabetes care", "The Lancet. Diabetes & endocrinology",
    "Clinical infectious diseases", "The Lancet. Infectious diseases",
    "American journal of respiratory and critical care medicine",
    "The Lancet. Neurology", "JAMA neurology",
    "Annals of the rheumatic diseases", "Arthritis & rheumatology",
    "The Lancet. Psychiatry", "Kidney international",
}


class PubMedFetcher:
    def __init__(self) -> None:
        self._limiter = AsyncTokenBucketLimiter(rate=10.0, capacity=10.0)
        self._http = httpx.AsyncClient(timeout=30.0)
        self._embedder = BGEEmbedder()
        self._qdrant = QdrantWriter()
        self._params_base: dict[str, str] = {"retmode": "json"}
        if settings.ncbi_api_key:
            self._params_base["api_key"] = settings.ncbi_api_key

    async def ingest_all_domains(self) -> None:
        for domain_query in _DOMAINS:
            logger.info("Fetching PubMed for: %s", domain_query)
            pmids = await self._esearch(domain_query, max_results=500)
            await self._fetch_and_ingest(pmids)

    async def fetch_by_pmids(self, pmids: list[str]) -> list[dict[str, Any]]:
        """Public method for on-demand retrieval during query time."""
        return await self._efetch_abstracts(pmids)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
    )
    async def _esearch(self, query: str, max_results: int = 100) -> list[str]:
        async with self._limiter:
            response = await self._http.get(
                f"{_NCBI_BASE}/esearch.fcgi",
                params={
                    **self._params_base,
                    "db": "pubmed",
                    "term": f"{query} AND ({settings.ncbi_recent_date_filter})",
                    "retmax": max_results,
                    "usehistory": "n",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("esearchresult", {}).get("idlist", [])

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        stop=stop_after_attempt(5),
    )
    async def _efetch_abstracts(self, pmids: list[str]) -> list[dict[str, Any]]:
        if not pmids:
            return []
        async with self._limiter:
            response = await self._http.get(
                f"{_NCBI_BASE}/efetch.fcgi",
                params={
                    **self._params_base,
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "rettype": "abstract",
                    "retmode": "xml",
                },
            )
            response.raise_for_status()
            return _parse_efetch_xml(response.text)

    async def _fetch_and_ingest(self, pmids: list[str]) -> None:
        articles = await self._efetch_abstracts(pmids)
        if not articles:
            return

        texts = [a["abstract"] for a in articles if a.get("abstract")]
        valid_articles = [a for a in articles if a.get("abstract")]

        if not texts:
            return

        dense_vecs, sparse_vecs = await self._embedder.embed_batch(texts)

        from shared.utils.chunker import DocumentChunk

        chunks = [
            DocumentChunk(
                text=a["abstract"],
                metadata=_article_to_metadata(a),
                token_count=len(a["abstract"]) // 4,
            )
            for a in valid_articles
        ]

        await self._qdrant.upsert_chunks(chunks, dense_vecs, sparse_vecs)
        logger.info("Ingested %d PubMed abstracts", len(chunks))


def _parse_efetch_xml(xml_text: str) -> list[dict[str, Any]]:
    """Parse NCBI efetch XML response into structured article dicts."""
    articles: list[dict[str, Any]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse NCBI XML response")
        return articles

    for article_elem in root.findall(".//PubmedArticle"):
        article: dict[str, Any] = {}

        # PMID
        pmid_elem = article_elem.find(".//PMID")
        article["pmid"] = pmid_elem.text if pmid_elem is not None else ""

        # Title
        title_elem = article_elem.find(".//ArticleTitle")
        article["title"] = title_elem.text or "" if title_elem is not None else ""

        # Abstract
        abstract_texts = article_elem.findall(".//AbstractText")
        article["abstract"] = " ".join(
            (elem.text or "") for elem in abstract_texts if elem.text
        )

        # Authors
        author_elems = article_elem.findall(".//Author")
        authors = []
        for a in author_elems[:3]:  # cap at 3 for display
            last = a.findtext("LastName", "")
            initials = a.findtext("Initials", "")
            if last:
                authors.append(f"{last} {initials}".strip())
        article["authors"] = ", ".join(authors) + (" et al." if len(author_elems) > 3 else "")

        # Journal
        article["journal"] = article_elem.findtext(".//Title", "")

        # Year
        year_elem = article_elem.find(".//PubDate/Year")
        article["pub_year"] = int(year_elem.text) if year_elem is not None and year_elem.text else 0

        # DOI
        doi_elem = article_elem.find(".//ArticleId[@IdType='doi']")
        article["doi"] = doi_elem.text if doi_elem is not None else ""

        # Doc type heuristic from publication type tags
        pub_types = [e.text for e in article_elem.findall(".//PublicationType") if e.text]
        article["doc_type"] = _classify_doc_type(pub_types)

        if article.get("abstract"):
            articles.append(article)

    return articles


def _classify_doc_type(pub_types: list[str]) -> str:
    """Classify document type from PubMed publication type tags."""
    types_lower = {t.lower() for t in pub_types}
    if "practice guideline" in types_lower or "guideline" in types_lower:
        return "guideline"
    if "meta-analysis" in types_lower:
        return "meta-analysis"
    if "systematic review" in types_lower:
        return "review"
    if "randomized controlled trial" in types_lower:
        return "trial"
    if "case reports" in types_lower:
        return "case_report"
    if "review" in types_lower:
        return "review"
    return "article"


def _classify_journal_tier(journal: str) -> int:
    """
    Assign evidence tier based on journal name.

    Tier hierarchy (from Hunt AI Medical Knowledge Graph):
      2 = International guidelines body journals
      3 = Big 4 general medical journals (NEJM, Lancet, JAMA, BMJ)
      4 = Specialty parent journals (Circulation, JCO, Gut, etc.)
      5 = Other indexed journals
    """
    if journal in _TIER3_JOURNALS:
        return 3
    if journal in _SPECIALTY_PARENT_JOURNALS:
        return 4
    return 5


def _article_to_metadata(article: dict[str, Any]) -> dict[str, Any]:
    journal = article.get("journal", "")
    doc_type = article.get("doc_type", "article")
    tier = _classify_journal_tier(journal)
    # Guidelines from any source get elevated to tier 2
    if doc_type == "guideline":
        tier = min(tier, 2)
    return {
        "source": "PubMed",
        "pmid": article.get("pmid", ""),
        "doi": article.get("doi", ""),
        "title": article.get("title", ""),
        "authors": article.get("authors", ""),
        "journal": journal,
        "pub_year": article.get("pub_year", 0),
        "doc_type": doc_type,
        "tier": tier,
        "is_open_access": False,
        "is_landmark": False,
    }
