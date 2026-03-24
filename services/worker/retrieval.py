"""
Hybrid retrieval + two-tier re-ranking pipeline.

Steps:
  1. Qdrant hybrid search (dense + sparse RRF fusion) with metadata pre-filters
  2. Concurrent NCBI live retrieval for research_question intent
  3. PMC BioC full-text for open-access articles (parallel with step 2)
  4. Tavily fallback if NCBI returns <5 results for 2023+
  5. Two-tier re-ranking:
     - Cohere Rerank 3.5 for ALL queries (default, multilingual, 392ms/50 docs)
     - MedCPT Cross-Encoder specifically for PubMed documents
  6. Tier-weighted + temporal score fusion → top-5 selection (avoid "lost in middle")
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Filter,
    FieldCondition,
    Range,
    MatchValue,
    FusionQuery,
    Prefetch,
    SparseVector,
    NamedSparseVector,
    NamedVector,
)

from shared.config import get_settings
from shared.models.query import QueryMessage
from services.ingestion.embedder import BGEEmbedder
from services.ingestion.pubmed_fetcher import PubMedFetcher, _classify_journal_tier
from services.ingestion.pmc_fetcher import PMCFetcher
from .reranker import cohere_rerank, medcpt_rerank
from .query_understanding import SPECIALTY_JOURNAL_PRIORITY

logger = logging.getLogger(__name__)
settings = get_settings()

_DENSE_VECTOR_NAME = "bge-m3-dense"
_SPARSE_VECTOR_NAME = "bge-m3-sparse"

# ── Evidence hierarchy for re-ranking (from Open Evidence analysis + Knowledge Graph Part 5.2)
# When specialty is detected, docs from specialty's governing journal get boosted.
TIER_WEIGHTS: dict[int, float] = {
    1: 1.00,  # ICMR / Indian guidelines (elevated for Indian-specific queries)
    2: 0.95,  # International guidelines (WHO, AHA, ESC, KDIGO, etc.)
    3: 0.90,  # Big 4: NEJM, Lancet, JAMA, BMJ
    4: 0.88,  # Other high-impact general journals
    5: 0.80,  # Specialist journals (Circulation, JCO, Gut, etc.)
    6: 0.85,  # Indian journals (JAPI, IJM, etc.)
    7: 0.60,  # Preprints
}

# ── Doc-type weights (from Open Evidence's evidence hierarchy) ─────────────────
# Society guidelines > meta-analyses > RCTs > cohort > reviews > case reports
DOC_TYPE_WEIGHTS: dict[str, float] = {
    "guideline": 1.00,
    "meta-analysis": 0.95,
    "trial": 0.90,
    "review": 0.80,
    "article": 0.75,
    "case_report": 0.65,
    "preprint": 0.55,
}

# ── Temporal recency multipliers ───────────────────────────────────────────────
YEAR_MULTIPLIERS: dict[int, float] = {
    2026: 1.00,
    2025: 1.00,
    2024: 0.97,
    2023: 0.94,
}
_LANDMARK_YEARS_MULTIPLIER = 0.85  # For pre-2023 landmark trials
_EXCLUDED_MULTIPLIER = 0.0          # For non-landmark pre-2020

# ── Specialty journal boost ────────────────────────────────────────────────────
# When a specialty is detected, docs from that specialty's priority journals
# get a multiplicative boost. This implements the "route to specialty journals"
# insight from the knowledge graph.
_SPECIALTY_JOURNAL_BOOST = 1.15


class HybridRetriever:
    def __init__(self) -> None:
        self._qdrant = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self._embedder = BGEEmbedder()
        self._pubmed = PubMedFetcher()
        self._pmc = PMCFetcher()
        self._http = httpx.AsyncClient(timeout=30.0)

    async def retrieve(self, msg: QueryMessage) -> list[dict[str, Any]]:
        """Full retrieval pipeline returning top-K ranked chunks."""
        query_text = msg.translated_text or msg.raw_text

        # 1. Embed the query
        dense_vecs, sparse_vecs = await self._embedder.embed_batch([query_text])
        dense_vec = dense_vecs[0]
        sparse_vec = sparse_vecs[0]

        # 2. Run Qdrant + NCBI + PMC BioC concurrently
        tasks: list[asyncio.Task[Any]] = [
            asyncio.create_task(
                self._qdrant_hybrid_search(dense_vec, sparse_vec, msg)
            )
        ]
        if msg.intent in ("research_question", "drug_interaction"):
            tasks.append(asyncio.create_task(self._ncbi_retrieve(msg)))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        qdrant_chunks: list[dict[str, Any]] = results[0] if not isinstance(results[0], Exception) else []
        ncbi_chunks: list[dict[str, Any]] = []
        if len(results) > 1 and not isinstance(results[1], Exception):
            ncbi_chunks = results[1]

        # 3. PMC BioC full-text for top PubMed results (parallel with Tavily)
        pmc_task = None
        ncbi_pmids = [c["pmid"] for c in ncbi_chunks if c.get("pmid")]
        if ncbi_pmids:
            pmc_task = asyncio.create_task(
                self._pmc.fetch_fulltext_by_pmids(ncbi_pmids, max_articles=5)
            )

        # 4. Tavily fallback if NCBI returns <5 recent results
        recent_ncbi = [c for c in ncbi_chunks if c.get("pub_year", 0) >= 2023]
        tavily_task = None
        if msg.intent == "research_question" and len(recent_ncbi) < 5:
            tavily_task = asyncio.create_task(self._tavily_fallback(query_text))

        # Await PMC + Tavily concurrently
        pmc_chunks: list[dict[str, Any]] = []
        if pmc_task:
            try:
                pmc_chunks = await pmc_task
            except Exception as e:
                logger.warning("PMC BioC fetch failed: %s", e)

        if tavily_task:
            try:
                ncbi_chunks.extend(await tavily_task)
            except Exception as e:
                logger.warning("Tavily fallback failed: %s", e)

        # Merge: prefer PMC full-text over abstract for same PMID
        pmc_pmids = {c["pmid"] for c in pmc_chunks if c.get("pmid")}
        ncbi_deduped = [c for c in ncbi_chunks if c.get("pmid") not in pmc_pmids]

        all_chunks = qdrant_chunks + ncbi_deduped + pmc_chunks

        # 5. Re-rank with Cohere + MedCPT
        reranked = await self._rerank(query_text, all_chunks)

        # 6. Apply tier + temporal + specialty + doc-type weighted scoring
        scored = _apply_weighted_scores(reranked, specialty=msg.specialty)

        # 7. For guideline queries, ensure guideline docs are promoted to top
        if msg.intent == "guideline_query":
            scored = _promote_guidelines(scored)

        # 8. Return top-K
        return scored[: settings.reranker_top_k]

    async def _qdrant_hybrid_search(
        self,
        dense_vec: list[float],
        sparse_vec: dict[int, float],
        msg: QueryMessage,
    ) -> list[dict[str, Any]]:
        """Qdrant Universal Query API with RRF fusion of dense + sparse."""
        # Build intent-specific filter
        must_conditions = [
            FieldCondition(key="pub_year", range=Range(gte=settings.min_pub_year))
        ]
        if msg.intent == "guideline_query":
            must_conditions.append(FieldCondition(key="tier", range=Range(lte=2)))
        elif msg.intent == "epidemiology":
            must_conditions.append(
                FieldCondition(key="source", match=MatchValue(value="ICMR_STW"))
            )

        prefetch = [
            Prefetch(
                query=NamedVector(name=_DENSE_VECTOR_NAME, vector=dense_vec),
                limit=settings.retrieval_prefetch_limit,
            ),
            Prefetch(
                query=NamedSparseVector(
                    name=_SPARSE_VECTOR_NAME,
                    vector=SparseVector(
                        indices=list(sparse_vec.keys()),
                        values=list(sparse_vec.values()),
                    ),
                ),
                limit=settings.retrieval_prefetch_limit,
            ),
        ]

        results = await self._qdrant.query_points(
            collection_name=settings.qdrant_collection_guidelines,
            prefetch=prefetch,
            query=FusionQuery(fusion="rrf"),
            query_filter=Filter(must=must_conditions),
            limit=settings.retrieval_final_limit,
            with_payload=True,
        )

        chunks = []
        for point in results.points:
            payload = dict(point.payload or {})
            payload["_qdrant_score"] = point.score
            chunks.append(payload)
        return chunks

    async def _ncbi_retrieve(self, msg: QueryMessage) -> list[dict[str, Any]]:
        """Live NCBI retrieval for research_question intent."""
        queries = msg.expanded_queries or [msg.translated_text or msg.raw_text]
        # Use the most expanded query for NCBI
        search_query = queries[-1] if queries else ""

        pmids = await self._pubmed._esearch(search_query, max_results=20)
        if not pmids:
            return []

        articles = await self._pubmed._efetch_abstracts(pmids[:20])
        return [
            {
                "text": a.get("abstract", ""),
                "title": a.get("title", ""),
                "authors": a.get("authors", ""),
                "journal": a.get("journal", ""),
                "pub_year": a.get("pub_year", 0),
                "doi": a.get("doi", ""),
                "pmid": a.get("pmid", ""),
                "source": "PubMed_live",
                "tier": _classify_journal_tier(a.get("journal", "")),
                "doc_type": a.get("doc_type", "article"),
                "is_landmark": False,
                "_qdrant_score": 0.0,
            }
            for a in articles
            if a.get("abstract")
        ]

    async def _tavily_fallback(self, query: str) -> list[dict[str, Any]]:
        """Tavily search for recent articles when NCBI returns insufficient 2023+ results."""
        if not settings.tavily_api_key:
            logger.warning("Tavily API key not configured; skipping fallback")
            return []

        try:
            response = await self._http.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.tavily_api_key,
                    "query": f"medical research {query} 2023 2024 2025",
                    "search_depth": "advanced",
                    "include_domains": ["pubmed.ncbi.nlm.nih.gov", "nejm.org", "thelancet.com"],
                    "max_results": 5,
                },
            )
            data = response.json()
        except httpx.HTTPError as e:
            logger.warning("Tavily request failed: %s", e)
            return []

        chunks = []
        for result in data.get("results", []):
            chunks.append({
                "text": result.get("content", ""),
                "title": result.get("title", ""),
                "source": "Tavily",
                "tier": 5,
                "pub_year": 2024,  # fallback year
                "doi": "",
                "is_landmark": False,
                "_qdrant_score": 0.0,
            })
        return chunks

    async def _rerank(
        self, query: str, chunks: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Two-tier re-ranking:
        1. Cohere Rerank 3.5 for all chunks (primary, multilingual)
        2. MedCPT for PubMed-specific chunks (secondary, biomedical SOTA)
        """
        if not chunks:
            return []

        # Tier 1: Cohere for everything
        chunks = await cohere_rerank(query, chunks)

        # Tier 2: MedCPT specifically for PubMed/PMC documents
        _PUBMED_SOURCES = {"PubMed", "PubMed_live", "PMC_fulltext"}
        pubmed_chunks = [c for c in chunks if c.get("source") in _PUBMED_SOURCES]
        other_chunks = [c for c in chunks if c.get("source") not in _PUBMED_SOURCES]

        if pubmed_chunks and settings.reranker_service_url:
            pubmed_chunks = await medcpt_rerank(
                query, pubmed_chunks, settings.reranker_service_url
            )

        return pubmed_chunks + other_chunks


def _apply_weighted_scores(
    chunks: list[dict[str, Any]], specialty: str | None = None
) -> list[dict[str, Any]]:
    """
    Apply tier + temporal + doc-type + specialty-journal weighted scoring.

    Scoring formula:
      final = base_reranker_score * tier_weight * year_mult * doc_type_weight * journal_boost

    The journal_boost rewards documents from the specialty's priority journals
    (e.g., Circulation/JACC for cardiology queries). This implements the
    "route to specialty journals" insight from the Medical Knowledge Graph.
    """
    # Build set of priority journal ISSNs for detected specialty
    priority_issns: set[str] = set()
    if specialty and specialty in SPECIALTY_JOURNAL_PRIORITY:
        priority_issns = set(SPECIALTY_JOURNAL_PRIORITY[specialty])

    for chunk in chunks:
        base_score = chunk.get("_reranker_score", 0.0)
        tier = chunk.get("tier", 5)
        pub_year = chunk.get("pub_year", 0)
        is_landmark = chunk.get("is_landmark", False)
        doc_type = chunk.get("doc_type", "article")

        tier_weight = TIER_WEIGHTS.get(tier, 0.75)
        doc_type_weight = DOC_TYPE_WEIGHTS.get(doc_type, 0.75)

        if pub_year >= 2023:
            year_mult = YEAR_MULTIPLIERS.get(pub_year, 0.94)
        elif 2020 <= pub_year < 2023:
            year_mult = _LANDMARK_YEARS_MULTIPLIER if is_landmark else 0.0
        else:
            year_mult = _LANDMARK_YEARS_MULTIPLIER if is_landmark else _EXCLUDED_MULTIPLIER

        # Specialty journal boost: reward docs from the specialty's priority journals
        journal_boost = 1.0
        if priority_issns and chunk.get("issn") in priority_issns:
            journal_boost = _SPECIALTY_JOURNAL_BOOST

        chunk["_final_score"] = (
            base_score * tier_weight * year_mult * doc_type_weight * journal_boost
        )

    return sorted(chunks, key=lambda c: c["_final_score"], reverse=True)


def _promote_guidelines(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    For guideline queries, ensure guideline-type documents appear first.

    This implements the "guideline-first routing" pattern from the Open Evidence
    analysis: when a query names a specific guideline, the answer should lead
    with the guideline itself, then expand with supporting evidence.
    """
    guidelines = [c for c in chunks if c.get("doc_type") == "guideline"]
    non_guidelines = [c for c in chunks if c.get("doc_type") != "guideline"]
    return guidelines + non_guidelines
