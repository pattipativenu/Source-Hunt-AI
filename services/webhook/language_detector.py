"""
Fast language detection for incoming WhatsApp messages.

Uses langdetect with a fallback to 'en' on failure.
For production, consider lingua-py for better accuracy on short Hinglish texts.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# BCP-47 codes for supported Indian languages
_SUPPORTED_CODES = {
    "hi", "bn", "te", "mr", "ta", "gu", "kn", "ml", "pa", "ur",
    "or", "as", "en",
}


def detect_language(text: str) -> str:
    """
    Detect the language of a text string.
    Returns a BCP-47 language code (e.g., 'hi', 'ta', 'en').
    Falls back to 'en' if detection fails or language is unsupported.
    """
    if not text or len(text.strip()) < 3:
        return "en"

    try:
        from langdetect import detect, LangDetectException  # type: ignore[import]
        code = detect(text)
        return code if code in _SUPPORTED_CODES else "en"
    except Exception as e:
        logger.debug("Language detection failed: %s", e)
        return "en"
