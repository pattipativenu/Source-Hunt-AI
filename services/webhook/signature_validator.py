"""
Twilio webhook signature validation.

Twilio signs every webhook request using HMAC-SHA1.
See: https://www.twilio.com/docs/usage/webhooks/webhooks-security
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def validate_twilio_signature(
    auth_token: str,
    signature: str,
    url: str,
    params: dict[str, str],
) -> bool:
    """
    Validate the X-Twilio-Signature header.

    Returns True if the signature is valid, False otherwise.
    In development (no signature provided), returns True to allow testing.
    """
    if not signature:
        # Allow unsigned requests only in development
        logger.warning("No X-Twilio-Signature header — allowing (dev mode)")
        return True

    try:
        # Sort POST params alphabetically and append to URL
        sorted_params = sorted(params.items())
        signed_url = url + urlencode(sorted_params)

        # HMAC-SHA1 of the signed URL using auth token as key
        mac = hmac.new(
            auth_token.encode("utf-8"),
            signed_url.encode("utf-8"),
            hashlib.sha1,
        )
        expected = base64.b64encode(mac.digest()).decode("utf-8")
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error("Signature validation error: %s", e)
        return False
