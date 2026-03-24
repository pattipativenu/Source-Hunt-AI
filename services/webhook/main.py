"""
Twilio WhatsApp webhook receiver.

Twilio sends an HTTP POST with form fields when a WhatsApp message arrives.
We must respond with TwiML within 5 seconds, so we:
  1. Validate X-Twilio-Signature
  2. Publish to Cloud Pub/Sub (async processing)
  3. Return an immediate TwiML ACK ("Searching…")

Sandbox setup (no business verification needed):
  console.twilio.com → Messaging → Try it out → Send a WhatsApp message
  Webhook URL: https://<your-ngrok>.ngrok.io/webhook/whatsapp
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import datetime

from fastapi import FastAPI, Form, Header, HTTPException, Request, status
from fastapi.responses import Response
from google.cloud import pubsub_v1
import redis.asyncio as aioredis

from shared.config import get_settings
from shared.models.query import QueryMessage
from .language_detector import detect_language
from .signature_validator import validate_twilio_signature

from shared.utils.cloud_logging import setup_logging

setup_logging("webhook")
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(title="Hunt AI Webhook")

_publisher = pubsub_v1.PublisherClient()
_topic_path = _publisher.topic_path(
    settings.gcp_project_id, settings.pubsub_topic_queries
)
_redis = aioredis.Redis(
    host=settings.redis_host, port=settings.redis_port, decode_responses=True
)

_WHATSAPP_PHONE_RE = re.compile(r"^whatsapp:\+[1-9]\d{6,14}$")

_ACK_TWIML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<Response>"
    "<Message>🔍 Searching ICMR guidelines + PubMed… I'll send results shortly.</Message>"
    "</Response>"
)


@app.post("/webhook/whatsapp")
async def twilio_webhook(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    x_twilio_signature: str | None = Header(default=None, alias="X-Twilio-Signature"),
) -> Response:
    """Receive inbound WhatsApp message from Twilio, ACK immediately, queue for processing."""
    raw_url = str(request.url)
    form_params = dict(await request.form())

    if not validate_twilio_signature(
        settings.twilio_auth_token, x_twilio_signature or "", raw_url, form_params
    ):
        logger.warning("Invalid Twilio signature from %s", From)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid signature")

    if not _WHATSAPP_PHONE_RE.match(From):
        logger.warning("Invalid phone format: %s", From)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone format")

    text = Body.strip()
    if not text:
        return Response(content=_ACK_TWIML, media_type="text/xml")

    # Deduplicate: same user + same text within 2h window → skip
    dedup_key = f"dedup:{hashlib.sha256(f'{From}:{text}'.encode()).hexdigest()}"
    already_seen = await _redis.set(
        dedup_key, "1", ex=settings.redis_ttl_dedup, nx=True
    )
    if not already_seen:
        logger.info("Duplicate message from %s — skipping: %.60s…", From, text)
        return Response(content=_ACK_TWIML, media_type="text/xml")

    language_code = detect_language(text)
    logger.info("Message from %s [%s]: %.60s…", From, language_code, text)

    msg = QueryMessage(
        message_id=str(uuid.uuid4()),
        user_phone=From,
        raw_text=text,
        language_code=language_code,
        received_at=datetime.utcnow(),
    )
    _publish_message(msg)

    return Response(content=_ACK_TWIML, media_type="text/xml")


@app.post("/webhook/status")
async def twilio_status(request: Request) -> Response:
    """Twilio delivery status callback — log and acknowledge."""
    form = dict(await request.form())
    logger.info("Delivery status: %s → %s", form.get("MessageSid"), form.get("MessageStatus"))
    return Response(status_code=204)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _publish_message(msg: QueryMessage) -> None:
    data = json.dumps(msg.model_dump(mode="json")).encode("utf-8")
    _publisher.publish(
        _topic_path,
        data=data,
        user_phone=msg.user_phone,
        language_code=msg.language_code,
    )
