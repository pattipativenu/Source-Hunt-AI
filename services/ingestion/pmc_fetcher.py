"""
PMC BioC full-text fetcher for open-access articles.

PMC's BioC API provides structured full-text XML for ~3.5M open-access
articles — methods, results, tables, and figures that abstracts lack.

API docs: https://www.ncbi.nlm.nih.gov/research/bionlp/APIs/BioC-PMC/

Why this matters for Hunt AI:
  - PubMed abstracts are ~250 words; full-text gives 5000+ words with
    dosing details, subgroup analyses, and trial methodology
  - For complex queries (EGFR exon 20 sequencing, biologic selection),
    the "Results" and "Discussion" sections contain critical evidence
  - BioC returns labeled sections, so we can extract only what we need
    and stay within token limits for reranking + generation

Rate limit: 3 req/s without API key, 10 req/s with NCBI API key.
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

logger = logging.getLogger(__name__)
settings = get_settings()

_BIOC_BASE = "https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml"
_EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Sections most useful for evidence synthesis (in priority order)
_PRIORITY_SECTIONS = [
    "RESULTS",
    "DISCUSS",       # matches "Discussion" and "Discussions"
    "CONCL",         # matches "Conclusion" and "Conclusions"
    "METHODS",
    "INTRO",
]

# Max tokens per section to avoid blowing up context window
_MAX_SECTION_TOKENS = 600


class PMCFetcher:
    """
    Fetches full-text open-access articles from PMC via:
    1. PMC ID conversion (PMID → PMCID via NCBI ID Converter)
    2. BioC XML retrieval for structured full-text
    3. Section extraction with priority-based truncation
    """

    def __init__(self) -> None:
        self._limiter = AsyncTokenBucketLimiter(rate=10.0, capacity=10.0)
        self._http = httpx.AsyncClient(timeout=30.0)
        self._api_key_param = (
            {"api_key": settings.ncbi_api_key} if settings.ncbi_api_key else {}
        )

    async def fetch_fulltext_by_pmids(
        self, pmids: list[str], max_articles: int = 5
    ) -> list[dict[str, Any]]:
        """
        Given PubMed IDs, convert to PMCIDs, fetch full-text, extract key sections.
        Returns list of article dicts with 'sections' field containing structured text.
        Only works for open-access articles available in PMC.
        """
        if not pmids:
            return []

        # Step 1: Convert PMIDs → PMCIDs (only OA articles have PMCIDs)
        pmcid_map = await self._convert_pmids_to_pmcids(pmids)
        if not pmcid_map:
            logger.info("No open-access PMC articles found for %d PMIDs", len(pmids))
            return []

        # Step 2: Fetch full-text for up to max_articles
        articles = []
        for pmid, pmcid in list(pmcid_map.items())[:max_articles]:
            article = await self._fetch_bioc_article(pmcid, pmid)
            if article:
                articles.append(article)

        logger.info(
            "PMC BioC: %d/%d PMIDs had OA full-text, fetched %d",
            len(pmcid_map), len(pmids), len(articles),
        )
        return articles

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        stop=stop_after_attempt(3),
    )
    async def _convert_pmids_to_pmcids(
        self, pmids: list[str]
    ) -> dict[str, str]:
        """Use NCBI ID Converter API to map PMIDs → PMCIDs."""
        async with self._limiter:
            response = await self._http.get(
                f"{_EFETCH_BASE}/elink.fcgi",
                params={
                    "dbfrom": "pubmed",
                    "db": "pmc",
                    "id": ",".join(pmids),
                    "retmode": "xml",
                    **self._api_key_param,
                },
            )
            response.raise_for_status()

        pmcid_map: dict[str, str] = {}
        try:
            root = ET.fromstring(response.text)
            for linkset in root.findall(".//LinkSet"):
                pmid_elem = linkset.find(".//IdList/Id")
                if pmid_elem is None or pmid_elem.text is None:
                    continue
                pmid = pmid_elem.text

                # Find the linked PMC ID
                for link in linkset.findall(".//Link/Id"):
                    if link.text:
                        pmcid_map[pmid] = f"PMC{link.text}"
                        break
        except ET.ParseError:
            logger.warning("Failed to parse NCBI elink XML")

        return pmcid_map

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=1, max=15),
        stop=stop_after_attempt(3),
    )
    async def _fetch_bioc_article(
        self, pmcid: str, pmid: str
    ) -> dict[str, Any] | None:
        """Fetch and parse a single article from PMC BioC API."""
        async with self._limiter:
            try:
                response = await self._http.get(
                    f"{_BIOC_BASE}/{pmcid}/unicode",
                    timeout=20.0,
                )
                if response.status_code != 200:
                    logger.debug("PMC BioC %s returned %d", pmcid, response.status_code)
                    return None
            except httpx.HTTPError as e:
                logger.debug("PMC BioC request failed for %s: %s", pmcid, e)
                return None

        return _parse_bioc_xml(response.text, pmcid, pmid)


def _parse_bioc_xml(
    xml_text: str, pmcid: str, pmid: str
) -> dict[str, Any] | None:
    """
    Parse BioC XML into a structured article dict with labeled sections.

    BioC structure:
    <collection>
      <document>
        <passage>
          <infon key="section_type">RESULTS</infon>
          <text>...</text>
        </passage>
      </document>
    </collection>
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse BioC XML for %s", pmcid)
        return None

    document = root.find(".//document")
    if document is None:
        return None

    # Extract metadata
    title = ""
    journal = ""
    year = 0
    doi = ""
    authors = ""

    for infon in document.findall("infon"):
        key = infon.get("key", "")
        val = infon.text or ""
        if key == "title":
            title = val
        elif key == "journal":
            journal = val
        elif key == "year":
            year = int(val) if val.isdigit() else 0
        elif key == "doi":
            doi = val
        elif key == "authors":
            authors = val

    # Extract sections with their types
    sections: dict[str, list[str]] = {}
    for passage in document.findall(".//passage"):
        section_type = ""
        for infon in passage.findall("infon"):
            if infon.get("key") == "section_type":
                section_type = (infon.text or "").upper()
                break

        text_elem = passage.find("text")
        if text_elem is None or not text_elem.text:
            continue
        text = text_elem.text.strip()
        if not text or len(text) < 20:
            continue

        if section_type not in sections:
            sections[section_type] = []
        sections[section_type].append(text)

    if not sections:
        return None

    # Build priority-ordered composite text from key sections
    composite_parts: list[str] = []
    total_tokens = 0

    for priority_prefix in _PRIORITY_SECTIONS:
        for section_name, paragraphs in sections.items():
            if section_name.startswith(priority_prefix):
                section_text = " ".join(paragraphs)
                section_tokens = len(section_text) // 4  # rough estimate
                if total_tokens + section_tokens > _MAX_SECTION_TOKENS * 3:
                    # Truncate to fit budget
                    remaining = (_MAX_SECTION_TOKENS * 3 - total_tokens) * 4
                    composite_parts.append(
                        f"[{section_name}] {section_text[:remaining]}..."
                    )
                    total_tokens = _MAX_SECTION_TOKENS * 3
                    break
                composite_parts.append(f"[{section_name}] {section_text}")
                total_tokens += section_tokens

        if total_tokens >= _MAX_SECTION_TOKENS * 3:
            break

    if not composite_parts:
        return None

    return {
        "text": "\n\n".join(composite_parts),
        "title": title,
        "authors": authors,
        "journal": journal,
        "pub_year": year,
        "doi": doi,
        "pmid": pmid,
        "pmcid": pmcid,
        "source": "PMC_fulltext",
        "tier": 3,  # same as PubMed high-impact
        "doc_type": "article",
        "is_open_access": True,
        "is_landmark": False,
        "_qdrant_score": 0.0,
        "sections_available": list(sections.keys()),
    }
