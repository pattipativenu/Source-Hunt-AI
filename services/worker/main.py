"""
Worker Cloud Run service entry point.

Receives Pub/Sub push messages from the hunt-ai-queries topic,
runs the RAG pipeline, and delivers via Twilio WhatsApp API.
"""

from __future__ import annotations

import base64
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

from shared.config import get_settings
from shared.models.query import QueryMessage
from .pipeline import RAGPipeline
from .whatsapp_sender import WhatsAppSender

from shared.utils.cloud_logging import setup_logging

setup_logging("worker")
logger = logging.getLogger(__name__)
settings = get_settings()

_pipeline: RAGPipeline | None = None
_sender: WhatsAppSender | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pipeline, _sender
    _pipeline = RAGPipeline()
    _sender = WhatsAppSender()
    logger.info("Worker pipeline and WhatsApp sender initialised.")
    yield
    if _pipeline:
        await _pipeline.close()
    if _sender:
        await _sender.close()


app = FastAPI(title="Hunt AI Worker", lifespan=lifespan)


class PubSubMessage(BaseModel):
    message: dict[str, Any]
    subscription: str


@app.post("/pubsub/push", status_code=status.HTTP_204_NO_CONTENT)
async def pubsub_push(body: PubSubMessage) -> None:
    """Handle Pub/Sub push subscription messages."""
    try:
        data_b64 = body.message.get("data", "")
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
        msg = QueryMessage(**payload)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to decode Pub/Sub message: %s", e)
        raise HTTPException(status_code=400, detail="Invalid message format")

    assert _pipeline is not None
    assert _sender is not None

    # Send typing indicator immediately (doctor sees '...')
    await _sender.send_typing_indicator(msg.user_phone)

    parts = await _pipeline.run(msg)
    await _sender.send_paginated(msg.user_phone, parts)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
