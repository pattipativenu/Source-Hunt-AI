"""
Reranker comparison engine for the Hunt AI playground.

Supports four backends:
  1. cohere      — Cohere Rerank 3.5 API  (cloud, multilingual, 392ms/50 docs)
  2. bge         — BAAI/bge-reranker-v2-m3 (local HF, 568M, multilingual)
  3. jina        — jinaai/jina-reranker-v2-base-multilingual (local HF, 278M)
  4. medcpt      — ncbi/MedCPT-Cross-Encoder (local HF, 110M, PubMed-specific)

All backends expose the same interface:
    rerank(query: str, documents: list[str]) -> list[RerankResult]
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RerankResult:
    index: int          # original position in input list
    text: str           # document text
    score: float        # reranker relevance score (higher = more relevant)
    rank: int           # 1-based rank after reranking
    latency_ms: float = 0.0


@dataclass
class RerankerOutput:
    name: str
    model_id: str
    results: list[RerankResult]
    total_latency_ms: float
    error: str | None = None


# ── Cohere ────────────────────────────────────────────────────────────────────

def rerank_cohere(query: str, documents: list[str], api_key: str) -> RerankerOutput:
    try:
        import cohere  # type: ignore[import]
    except ImportError:
        return RerankerOutput("Cohere Rerank 3.5", "rerank-v3.5", [], 0, "cohere not installed")

    t0 = time.perf_counter()
    try:
        client = cohere.Client(api_key)
        response = client.rerank(
            model="rerank-v3.5",
            query=query,
            documents=documents,
            top_n=len(documents),
            return_documents=False,
        )
        latency = (time.perf_counter() - t0) * 1000

        results = [
            RerankResult(
                index=r.index,
                text=documents[r.index],
                score=r.relevance_score,
                rank=i + 1,
                latency_ms=latency,
            )
            for i, r in enumerate(response.results)
        ]
        return RerankerOutput("Cohere Rerank 3.5", "rerank-v3.5", results, latency)
    except Exception as e:
        return RerankerOutput("Cohere Rerank 3.5", "rerank-v3.5", [], 0, str(e))


# ── HuggingFace cross-encoder (generic) ──────────────────────────────────────

def _hf_rerank(
    name: str,
    model_id: str,
    query: str,
    documents: list[str],
    model_cache: dict[str, Any],
) -> RerankerOutput:
    """Load model once (cached), score all [query, doc] pairs."""
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore[import]
        import torch
    except ImportError:
        return RerankerOutput(name, model_id, [], 0, "transformers/torch not installed")

    try:
        if model_id not in model_cache:
            tokenizer = AutoTokenizer.from_pretrained(model_id)
            model = AutoModelForSequenceClassification.from_pretrained(model_id)
            model_cache[model_id] = (tokenizer, model)

        tokenizer, model = model_cache[model_id]
        pairs = [[query, doc] for doc in documents]

        t0 = time.perf_counter()
        with torch.no_grad():
            enc = tokenizer(
                pairs, truncation=True, padding=True,
                max_length=512, return_tensors="pt"
            )
            scores = model(**enc).logits.squeeze(-1).tolist()
        latency = (time.perf_counter() - t0) * 1000

        if isinstance(scores, float):
            scores = [scores]

        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        results = [
            RerankResult(
                index=orig_idx,
                text=documents[orig_idx],
                score=score,
                rank=rank + 1,
                latency_ms=latency,
            )
            for rank, (orig_idx, score) in enumerate(ranked)
        ]
        return RerankerOutput(name, model_id, results, latency)
    except Exception as e:
        return RerankerOutput(name, model_id, [], 0, str(e))


def rerank_bge(query: str, documents: list[str], model_cache: dict) -> RerankerOutput:
    """BAAI/bge-reranker-v2-m3 — 568M params, multilingual, Apache 2.0."""
    return _hf_rerank(
        "BGE Reranker v2-m3 (BAAI)",
        "BAAI/bge-reranker-v2-m3",
        query, documents, model_cache,
    )


def rerank_jina(query: str, documents: list[str], model_cache: dict) -> RerankerOutput:
    """jinaai/jina-reranker-v2-base-multilingual — 278M params, multilingual."""
    return _hf_rerank(
        "Jina Reranker v2 Multilingual",
        "jinaai/jina-reranker-v2-base-multilingual",
        query, documents, model_cache,
    )


def rerank_medcpt(query: str, documents: list[str], model_cache: dict) -> RerankerOutput:
    """ncbi/MedCPT-Cross-Encoder — 110M params, PubMed-trained, SOTA biomedical."""
    return _hf_rerank(
        "MedCPT Cross-Encoder (NCBI)",
        "ncbi/MedCPT-Cross-Encoder",
        query, documents, model_cache,
    )
