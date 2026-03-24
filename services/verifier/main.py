"""
DeBERTa NLI citation verifier service.

Deployed as CPU-only Cloud Run service (DeBERTa-v3-large fits in 2GB RAM).
Uses RAGHalu-style NLI to classify each (claim, premise) pair as:
  SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE

POST /verify
  Body: {"claim": str, "premise": str}
  Returns: {"label": str, "confidence": float}
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Literal

import torch
from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_pipeline_nli: Any | None = None

# DeBERTa NLI label ordering: [contradiction, neutral, entailment]
_LABEL_MAP = {
    "LABEL_0": "CONTRADICTED",
    "LABEL_1": "INSUFFICIENT_EVIDENCE",
    "LABEL_2": "SUPPORTED",
    # HuggingFace pipeline may return named labels
    "contradiction": "CONTRADICTED",
    "neutral": "INSUFFICIENT_EVIDENCE",
    "entailment": "SUPPORTED",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline_nli
    logger.info("Loading DeBERTa NLI model…")
    from transformers import pipeline as hf_pipeline  # type: ignore[import]
    _pipeline_nli = hf_pipeline(
        "zero-shot-classification",
        model="cross-encoder/nli-deberta-v3-large",
        device=-1,  # CPU
    )
    logger.info("DeBERTa NLI model loaded.")
    yield


app = FastAPI(title="Hunt AI Citation Verifier", lifespan=lifespan)


class VerifyRequest(BaseModel):
    claim: str
    premise: str


class VerifyResponse(BaseModel):
    label: Literal["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
    confidence: float


@app.post("/verify", response_model=VerifyResponse)
async def verify(body: VerifyRequest) -> VerifyResponse:
    if not body.claim or not body.premise:
        return VerifyResponse(label="INSUFFICIENT_EVIDENCE", confidence=0.0)

    assert _pipeline_nli is not None

    # Use the premise as the sequence and claim as the hypothesis
    result = _pipeline_nli(
        body.premise[:512],
        candidate_labels=["entailment", "neutral", "contradiction"],
        hypothesis_template="{}",
    )

    # Map the top label
    labels = result["labels"]
    scores = result["scores"]
    top_label = labels[0]
    top_score = scores[0]

    mapped = _LABEL_MAP.get(top_label, "INSUFFICIENT_EVIDENCE")

    # Apply confidence threshold from settings
    from shared.config import get_settings
    threshold = get_settings().nli_confidence_threshold
    if mapped == "SUPPORTED" and top_score < threshold:
        mapped = "INSUFFICIENT_EVIDENCE"

    return VerifyResponse(label=mapped, confidence=round(top_score, 4))  # type: ignore[arg-type]


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model": "cross-encoder/nli-deberta-v3-large"}
