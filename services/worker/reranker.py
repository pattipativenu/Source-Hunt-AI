"""
Two-tier re-ranking strategy (from blueprint):

Tier 1 — Cohere Rerank 3.5 (DEFAULT for ALL queries):
  - Zero infrastructure, single API call
  - 392ms latency for 50 documents
  - 100+ languages including Hindi/Telugu
  - $2 per 1,000 searches → ~$60/month at scale
  - Falls back to BGE-based scores if Cohere unavailable

Tier 2 — MedCPT Cross-Encoder (PubMed-SPECIFIC retrieval):
  - Trained on 18M PubMed query-article pairs
  - SOTA on 3/5 biomedical BEIR tasks
  - 110M params, runs on CPU
  - Only used when source is PubMed (not ICMR/drug lookups)
  - 512-token context, English-only (Cohere handles multilingual)
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def cohere_rerank(
    query: str,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Re-rank documents using Cohere Rerank 3.5 API.
    Falls back to original order if Cohere is unavailable.
    """
    if not settings.cohere_api_key:
        logger.warning("No Cohere API key — skipping reranking, using retrieval scores")
        return documents

    texts = [d.get("text", "")[:500] for d in documents]  # abstracts fit under 500 tokens

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                "https://api.cohere.com/v2/rerank",
                headers={
                    "Authorization": f"Bearer {settings.cohere_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "rerank-v3.5",
                    "query": query,
                    "documents": texts,
                    "top_n": len(texts),
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        logger.warning("Cohere rerank failed: %s — falling back to original order", e)
        return documents

    results = data.get("results", [])
    # Map relevance scores back to documents preserving all metadata
    for result in results:
        idx = result["index"]
        documents[idx]["_reranker_score"] = result["relevance_score"]
        documents[idx]["_reranker"] = "cohere-rerank-3.5"

    # Documents not scored by Cohere (shouldn't happen) get score 0
    for doc in documents:
        if "_reranker_score" not in doc:
            doc["_reranker_score"] = 0.0

    return sorted(documents, key=lambda d: d["_reranker_score"], reverse=True)


async def medcpt_rerank(
    query: str,
    documents: list[dict[str, Any]],
    medcpt_url: str,
) -> list[dict[str, Any]]:
    """
    Re-rank PubMed-sourced documents using the MedCPT Cross-Encoder service.
    Only called for PubMed documents when the MedCPT service is available.
    """
    texts = [d.get("text", "") for d in documents]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{medcpt_url}/rerank",
                json={"query": query, "documents": texts},
            )
            scores = response.json().get("scores", [])
            for doc, score in zip(documents, scores):
                doc["_reranker_score"] = score
                doc["_reranker"] = "medcpt"
    except httpx.HTTPError as e:
        logger.warning("MedCPT rerank failed: %s", e)

    return sorted(documents, key=lambda d: d.get("_reranker_score", 0.0), reverse=True)
