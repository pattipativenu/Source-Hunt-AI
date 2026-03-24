"""
Structure-aware chunker for parsed markdown documents (ICMR PDFs via Marker).

Rules:
- Respect document hierarchy: Volume → Chapter → Section → Subsection
- Target chunk size: ~512 tokens with 64-token overlap
- Never split markdown tables — treat them as atomic chunks
- Tag every chunk with source metadata
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DocumentChunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0


_TABLE_RE = re.compile(r"(\|.+\|[\r\n]+(?:\|[-: |]+\|[\r\n]+)(?:\|.+\|[\r\n]*)+)", re.MULTILINE)
_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

# Rough token estimator (GPT/Gemini tokeniser ≈ 4 chars/token for English medical text)
_CHARS_PER_TOKEN = 4
_TARGET_TOKENS = 512
_OVERLAP_TOKENS = 64
_TARGET_CHARS = _TARGET_TOKENS * _CHARS_PER_TOKEN
_OVERLAP_CHARS = _OVERLAP_TOKENS * _CHARS_PER_TOKEN


class StructureAwareChunker:
    def chunk_document(self, markdown: str, base_metadata: dict[str, Any]) -> list[DocumentChunk]:
        """
        Split a full markdown document into overlapping chunks.
        Tables are extracted first as atomic units; the remaining prose
        is split by heading boundaries then by character window.
        """
        chunks: list[DocumentChunk] = []
        table_spans: list[tuple[int, int]] = []

        # 1. Extract tables first to protect them from splitting
        for m in _TABLE_RE.finditer(markdown):
            chunks.append(
                DocumentChunk(
                    text=m.group(0).strip(),
                    metadata={**base_metadata, "chunk_type": "table"},
                    token_count=len(m.group(0)) // _CHARS_PER_TOKEN,
                )
            )
            table_spans.append((m.start(), m.end()))

        # 2. Build prose-only text by masking table spans
        prose = _mask_spans(markdown, table_spans)

        # 3. Split prose by heading boundaries to get section blocks
        section_blocks = _split_by_headings(prose)

        # 4. Slide a character window over each section block with overlap
        section_meta = dict(base_metadata)
        for block_heading, block_text in section_blocks:
            _update_section_meta(section_meta, block_heading)
            for chunk_text in _sliding_window(block_text, _TARGET_CHARS, _OVERLAP_CHARS):
                if not chunk_text.strip():
                    continue
                chunks.append(
                    DocumentChunk(
                        text=chunk_text.strip(),
                        metadata={**section_meta, "chunk_type": "prose"},
                        token_count=len(chunk_text) // _CHARS_PER_TOKEN,
                    )
                )

        return chunks


def _mask_spans(text: str, spans: list[tuple[int, int]]) -> str:
    """Replace table spans with blank lines so heading detection still works."""
    chars = list(text)
    for start, end in spans:
        for i in range(start, min(end, len(chars))):
            chars[i] = "\n" if chars[i] == "\n" else " "
    return "".join(chars)


def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """Return list of (heading_line, block_text) tuples."""
    positions = [(m.start(), m.group(0)) for m in _HEADING_RE.finditer(text)]
    if not positions:
        return [("", text)]

    blocks: list[tuple[str, str]] = []
    for idx, (pos, heading) in enumerate(positions):
        next_pos = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        block_text = text[pos:next_pos]
        blocks.append((heading, block_text))

    return blocks


def _sliding_window(text: str, window: int, overlap: int) -> list[str]:
    """Produce overlapping character windows over prose text."""
    if len(text) <= window:
        return [text]

    chunks: list[str] = []
    step = window - overlap
    start = 0
    while start < len(text):
        end = start + window
        chunks.append(text[start:end])
        start += step

    return chunks


def _update_section_meta(meta: dict[str, Any], heading: str) -> None:
    """Infer chapter/section from heading depth."""
    m = _HEADING_RE.match(heading)
    if not m:
        return
    level = len(m.group(1))  # number of '#' chars
    title = m.group(2).strip()
    if level == 1:
        meta["volume"] = title
    elif level == 2:
        meta["chapter"] = title
    elif level == 3:
        meta["section"] = title
    elif level == 4:
        meta["subsection"] = title
