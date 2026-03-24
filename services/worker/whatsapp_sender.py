"""
Twilio WhatsApp message sender.

Uses Twilio REST API to send response parts back to the doctor.
Sandbox: doctors first join via "join <word>-<word>" — then receive replies for free.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from shared.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_TWILIO_BASE = "https://api.twilio.com/2010-04-01/Accounts"


class WhatsAppSender:
    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=15.0,
        )
        self._messages_url = (
            f"{_TWILIO_BASE}/{settings.twilio_account_sid}/Messages.json"
        )

    async def send_text(self, to: str, body: str) -> None:
        """Send a plain text WhatsApp message."""
        await self._post({"From": settings.twilio_whatsapp_number, "To": to, "Body": body})

    async def send_paginated(self, to: str, parts: list[str]) -> None:
        """Send multiple message parts sequentially."""
        for part in parts:
            await self.send_text(to, part)

    async def send_typing_indicator(self, to: str) -> None:
        """Send an immediate ACK message while pipeline runs."""
        await self.send_text(to, "🔍 Searching ICMR guidelines + PubMed…")

    async def _post(self, data: dict[str, Any]) -> None:
        try:
            response = await self._http.post(self._messages_url, data=data)
            if response.status_code not in (200, 201):
                logger.error(
                    "Twilio send failed (%d): %s", response.status_code, response.text[:200]
                )
        except httpx.HTTPError as e:
            logger.error("Twilio send error: %s", e)

    async def close(self) -> None:
        await self._http.aclose()
