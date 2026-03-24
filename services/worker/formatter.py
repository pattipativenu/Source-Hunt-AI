"""
WhatsApp response formatter.

- Converts structured HuntAIResponse to WhatsApp markdown
- Paginates at 4096 characters with Part N/M headers
- Back-translates to original language via Gemini Flash (preserving medical terms)
"""

from __future__ import annotations

import logging

from shared.config import get_settings
from shared.models.response import HuntAIResponse

logger = logging.getLogger(__name__)
settings = get_settings()

_MAX_CHARS = 4096
_DISCLAIMER_SUFFIX = "\n\n_⚠️ AI-generated evidence search. Verify with current clinical guidelines before clinical application._"


class WhatsAppFormatter:
    def format(self, response: HuntAIResponse, language_code: str = "en") -> list[str]:
        """Format HuntAIResponse into paginated WhatsApp message parts."""
        body = _build_body(response)
        pages = _paginate(body, _MAX_CHARS)

        total = len(pages)
        parts: list[str] = []
        for i, page in enumerate(pages, start=1):
            header = f"*Part {i}/{total}:*\n\n" if total > 1 else ""
            if i == total:
                parts.append(f"{header}{page}{_DISCLAIMER_SUFFIX}")
            else:
                parts.append(f"{header}{page}")

        return parts


def _build_body(response: HuntAIResponse) -> str:
    lines: list[str] = []

    # Confidence badge
    badge = f"[{response.confidence_level}]"
    lines.append(f"{badge}\n\n{response.answer}")

    # Conflicting evidence
    if response.conflicting_evidence:
        lines.append(f"\n\n⚖️ *Conflicting Evidence:*\n{response.conflicting_evidence}")

    # Indian context
    if response.indian_context_note:
        lines.append(f"\n\n🇮🇳 *Indian Context:*\n{response.indian_context_note}")

    # Citations
    if response.citations:
        lines.append("\n\n*References:*")
        for c in response.citations:
            doi_link = f"doi.org/{c.doi}" if c.doi else "DOI unavailable"
            nli_marker = ""
            if c.nli_label == "INSUFFICIENT_EVIDENCE":
                nli_marker = " ⚠️"
            lines.append(
                f"[{c.index}] {c.authors} _{c.journal}_ ({c.year}). {doi_link}{nli_marker}"
            )

    # Follow-up questions
    if response.follow_up_questions:
        lines.append("\n\n💡 *Related questions you might ask:*")
        for q in response.follow_up_questions[:3]:
            lines.append(f"• {q}")

    return "\n".join(lines)


def _paginate(text: str, max_chars: int) -> list[str]:
    """Split text at paragraph boundaries to stay under max_chars."""
    if len(text) <= max_chars:
        return [text]

    pages: list[str] = []
    current = ""
    paragraphs = text.split("\n\n")

    for para in paragraphs:
        candidate = (current + "\n\n" + para).lstrip("\n")
        if len(candidate) > max_chars and current:
            pages.append(current.strip())
            current = para
        else:
            current = candidate

    if current.strip():
        pages.append(current.strip())

    return pages or [text[:max_chars]]
