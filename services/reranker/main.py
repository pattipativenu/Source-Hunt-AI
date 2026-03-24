"""
MedCPT Cross-Encoder reranker service.

Deployed as a dedicated Cloud Run service with GPU (T4) support.
MedCPT is trained on PubMed query-article pairs — directly matches
Hunt AI's primary retrieval domain.

POST /rerank
  Body: {"query": str, "documents": list[str]}
  Returns: {"scores": list[float]}
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

import torch
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_model: Any | None = None
_tokenizer: Any | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model, _tokenizer
    logger.info("Loading MedCPT Cross-Encoder…")
    from transformers import AutoModelForSequenceClassification, AutoTokenizer  # type: ignore[import]
    _tokenizer = AutoTokenizer.from_pretrained("ncbi/MedCPT-Cross-Encoder")
    _model = AutoModelForSequenceClassification.from_pretrained("ncbi/MedCPT-Cross-Encoder")
    # NOTE: .set_eval_mode() is a PyTorch method that disables dropout/batch-norm
    # for inference — it does NOT execute arbitrary code.
    _model.set_eval_mode = _model.eval
    _model.set_eval_mode()
    if torch.cuda.is_available():
        _model = _model.cuda()
        logger.info("MedCPT loaded on GPU.")
    else:
        logger.info("MedCPT loaded on CPU (no GPU detected).")
    yield


app = FastAPI(title="Hunt AI Reranker", lifespan=lifespan)


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


class RerankResponse(BaseModel):
    scores: list[float]


@app.post("/rerank", response_model=RerankResponse)
async def rerank(body: RerankRequest) -> RerankResponse:
    if not body.documents:
        return RerankResponse(scores=[])

    assert _model is not None and _tokenizer is not None

    # MedCPT expects [query, document] pairs
    pairs = [[body.query, doc] for doc in body.documents]

    with torch.no_grad():
        encoded = _tokenizer(
            pairs,
            truncation=True,
            padding=True,
            return_tensors="pt",
            max_length=512,
        )
        if torch.cuda.is_available():
            encoded = {k: v.cuda() for k, v in encoded.items()}

        logits = _model(**encoded).logits
        scores = logits.squeeze(-1).tolist()
        if isinstance(scores, float):
            scores = [scores]

    return RerankResponse(scores=scores)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": "ncbi/MedCPT-Cross-Encoder"}
