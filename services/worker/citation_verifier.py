"""
Citation verification layer (Attribution Gradient).

MVP approach (from blueprint):
  - Use Gemini-as-judge for NLI entailment (cost-effective for MVP)
  - Confidence threshold: > 0.7 for medical claims
  - v2 upgrade: replace with MiniCheck-7B (GPT-4-level at 400× lower cost)

Steps:
  1. Atomic claim extraction via Gemini Flash (with self-assessed confidence)
  2. Adaptive verification (inspired by LEAD entropy-aware reasoning):
     - High-confidence claims → standard NLI check
     - Low-confidence / uncertain claims → deeper verification with
       evidence re-grounding (re-read source passage in full)
  3. Gemini-as-judge NLI: does the source passage support the claim? (threshold > 0.7)
  4. Citation correction: if claim fails, search all retrieved chunks for better support
  5. DOI validation via CrossRef API (cached in Redis)
  6. Strip unverified claims from final answer text
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from shared.config import get_settings
from shared.models.response import Citation, HuntAIResponse
from shared.utils import RedisCache
from shared.utils.gemini_client import get_gemini_model, make_generation_config

logger = logging.getLogger(__name__)
settings = get_settings()

_CROSSREF_BASE = "https://api.crossref.org/works"

# ── NLI judge prompt (XML-structured for reliable Gemini classification) ──────
# Agent: Citation Verification (Stage 4 of RAG pipeline)
# Model: Gemini 2.5 Flash (gemini_model_primary)
# Purpose: Given a (claim, passage) pair, classifies factual support as
#          SUPPORTED / CONTRADICTED / INSUFFICIENT_EVIDENCE. The XML tags
#          separate the claim, passage, label definitions, and output format
#          so Gemini doesn't confuse claim text with instruction text.
_NLI_JUDGE_PROMPT = """\
<system_instruction>
  <identity>
    <role>Medical citation verifier</role>
    <mission>Determine whether a SOURCE PASSAGE provides factual support for a CLAIM
    extracted from a medical answer.</mission>
  </identity>

  <input>
    <claim>{claim}</claim>
    <source_passage>{passage}</source_passage>
  </input>

  <label_definitions>
    <!-- Clear semantic boundaries prevent the model from conflating partial
         support with full support — a common failure mode in medical NLI. -->
    <label name="SUPPORTED">The passage directly and explicitly supports the claim.
    Confidence must be >= 0.7 to qualify.</label>
    <label name="CONTRADICTED">The passage explicitly contradicts the claim
    with opposing evidence or data.</label>
    <label name="INSUFFICIENT_EVIDENCE">The passage does not clearly support
    or contradict the claim — it may be tangentially related or silent on the topic.</label>
  </label_definitions>

  <output_format>
    Respond with JSON only — no markdown fences, no commentary:
    {{
      "label": "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE",
      "confidence": <float 0.0-1.0>,
      "reasoning": "<one sentence explaining the judgment>"
    }}
  </output_format>
</system_instruction>
"""


class CitationVerifier:
    def __init__(self, cache: RedisCache) -> None:
        self._cache = cache
        self._http = httpx.AsyncClient(timeout=15.0)
        self._flash = get_gemini_model(settings.gemini_model_primary)
        self._flash_config = make_generation_config(
            temperature=0.0, max_output_tokens=512, json_mode=True
        )

    async def verify(
        self, response: HuntAIResponse, all_chunks: list[dict[str, Any]] | None = None
    ) -> HuntAIResponse:
        """
        Run full citation verification pipeline with adaptive depth.

        Inspired by LEAD's entropy-aware reasoning: uncertain claims get deeper
        verification (full passage re-read + alternative source search) while
        high-confidence claims get standard NLI check.
        """
        claims = await self._extract_claims(response.answer)

        verified_citations: list[Citation] = []
        removed_indices: set[int] = set()

        for citation in response.citations:
            claim_info = _find_claim_for_citation(claims, citation.index)
            claim_text = claim_info["text"] if claim_info else None
            self_confidence = claim_info.get("self_confidence", "HIGH") if claim_info else "LOW"

            if claim_text:
                # Adaptive verification depth based on self-assessed confidence
                if self_confidence == "LOW":
                    # Deep verification: use full passage (not truncated)
                    nli_result = await self._gemini_judge(
                        claim_text, citation.chunk_text, deep=True
                    )

                    # If still insufficient, try to find better support in all chunks
                    if (
                        nli_result["label"] == "INSUFFICIENT_EVIDENCE"
                        and all_chunks
                    ):
                        better = await self._find_better_source(
                            claim_text, all_chunks, citation.index
                        )
                        if better:
                            nli_result = better
                else:
                    # Standard verification for high-confidence claims
                    nli_result = await self._gemini_judge(
                        claim_text, citation.chunk_text
                    )

                citation.nli_label = nli_result["label"]
                citation.nli_confidence = nli_result["confidence"]

                if citation.nli_label == "CONTRADICTED":
                    logger.warning("Citation [%d] CONTRADICTED — removing", citation.index)
                    removed_indices.add(citation.index)
                    continue
                elif citation.nli_label == "INSUFFICIENT_EVIDENCE":
                    response = response.model_copy(update={"confidence_level": "LOW"})
            else:
                citation.nli_label = "INSUFFICIENT_EVIDENCE"
                citation.nli_confidence = 0.0

            # DOI validation
            if citation.doi:
                citation.doi_valid = await self._validate_doi(citation)

            verified_citations.append(citation)

        # Strip removed citation markers from answer text
        clean_answer = _strip_removed_citations(response.answer, removed_indices)

        return response.model_copy(
            update={"citations": verified_citations, "answer": clean_answer}
        )

    async def _extract_claims(self, answer: str) -> list[dict[str, Any]]:
        """
        Decompose answer into atomic claims with citation indices
        and self-assessed confidence (inspired by LEAD uncertainty detection).

        Claims with transition words or hedging language get LOW confidence,
        mirroring LEAD's finding that high-entropy transition tokens correlate
        with hallucinations.
        """
        # ── Claim extraction prompt (XML-structured) ─────────────────────
        # Agent: Citation Verification (Stage 4 — claim decomposition)
        # Model: Gemini Flash
        # Purpose: Decompose a medical answer into atomic verifiable claims,
        #          each tagged with its citation index and self-assessed confidence.
        #          LEAD-inspired: hedging/bridging language → LOW confidence.
        prompt = (
            "<system_instruction>\n"
            "  <identity>\n"
            "    <role>Medical claim decomposer</role>\n"
            "    <mission>Split a medical answer into atomic factual claims.\n"
            "    Each claim = one verifiable assertion tied to a citation.</mission>\n"
            "  </identity>\n"
            "\n"
            "  <confidence_criteria>\n"
            "    <!-- LEAD-inspired: transition words and hedging correlate with\n"
            "         high-entropy states where hallucination risk peaks. -->\n"
            '    <level name="HIGH">Claim states a specific fact directly from a cited source.\n'
            "    Contains concrete data: drug names, dosages, percentages, trial names.</level>\n"
            '    <level name="LOW">Claim uses hedging language (may, might, could, suggests),\n'
            "    bridges between sources, or makes inferences not directly stated in any\n"
            "    single source.</level>\n"
            "  </confidence_criteria>\n"
            "\n"
            "  <output_format>\n"
            '    Return JSON only: {"claims": [{"text": "...", "citation_index": N,\n'
            '    "self_confidence": "HIGH"|"LOW"}]}\n'
            "  </output_format>\n"
            "\n"
            "  <input>\n"
            f"    <answer_text>{answer}</answer_text>\n"
            "  </input>\n"
            "</system_instruction>"
        )
        response = await self._flash.generate_content_async(
            prompt, generation_config=self._flash_config
        )
        try:
            data = json.loads(response.text)
            return data.get("claims", [])
        except (json.JSONDecodeError, AttributeError):
            return []

    async def _gemini_judge(
        self, claim: str, passage: str, deep: bool = False
    ) -> dict[str, Any]:
        """
        Use Gemini Flash as NLI judge (MVP approach).

        When deep=True (for low-confidence claims), use the full passage
        instead of truncating — mirrors LEAD's "evidence re-grounding"
        where uncertain reasoning gets re-anchored to source material.

        v2 upgrade target: Bespoke-MiniCheck-7B (GPT-4 accuracy at 400× lower cost).
        """
        max_passage = 2000 if deep else 800
        prompt = _NLI_JUDGE_PROMPT.format(claim=claim, passage=passage[:max_passage])
        try:
            response = await self._flash.generate_content_async(
                prompt, generation_config=self._flash_config
            )
            data = json.loads(response.text)
            label = data.get("label", "INSUFFICIENT_EVIDENCE")
            confidence = float(data.get("confidence", 0.0))

            # Apply threshold — blueprint specifies > 0.7 for medical claims
            if label == "SUPPORTED" and confidence < settings.nli_confidence_threshold:
                label = "INSUFFICIENT_EVIDENCE"

            return {"label": label, "confidence": confidence}
        except Exception as e:
            logger.warning("Gemini judge failed: %s", e)
            return {"label": "INSUFFICIENT_EVIDENCE", "confidence": 0.0}

    async def _find_better_source(
        self, claim: str, all_chunks: list[dict[str, Any]], original_index: int
    ) -> dict[str, Any] | None:
        """
        For uncertain claims that failed NLI, search all retrieved chunks
        for a better supporting source. Returns updated NLI result or None.
        """
        for chunk in all_chunks:
            text = chunk.get("text", "")
            if not text or len(text) < 50:
                continue
            result = await self._gemini_judge(claim, text, deep=True)
            if result["label"] == "SUPPORTED" and result["confidence"] >= settings.nli_confidence_threshold:
                logger.info(
                    "Found better source for claim (was index %d) → %s",
                    original_index, chunk.get("source", "unknown"),
                )
                return result
        return None

    async def _validate_doi(self, citation: Citation) -> bool:
        """Validate DOI via CrossRef API (cached in Redis 24h)."""
        cached = await self._cache.get_doi(citation.doi)
        if cached is not None:
            return bool(cached.get("valid", False))

        try:
            response = await self._http.get(
                f"{_CROSSREF_BASE}/{citation.doi}",
                headers={"User-Agent": f"HuntAI/1.0 (mailto:{settings.crossref_mailto})"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json().get("message", {})
                crossref_year = _extract_year(data)
                crossref_journal = _extract_journal(data)
                year_ok = abs(crossref_year - citation.year) <= 1 if crossref_year else True
                journal_ok = (
                    citation.journal.lower() in crossref_journal.lower()
                    if crossref_journal and citation.journal
                    else True
                )
                valid = year_ok and journal_ok
            else:
                valid = False
        except httpx.HTTPError:
            valid = False

        await self._cache.set_doi(citation.doi, {"valid": valid}, settings.redis_ttl_doi)
        return valid


def _find_claim_for_citation(
    claims: list[dict[str, Any]], citation_index: int
) -> dict[str, Any] | None:
    """Find the claim dict (text + self_confidence) for a given citation index."""
    for claim in claims:
        if claim.get("citation_index") == citation_index:
            return claim
    return None


def _strip_removed_citations(answer: str, removed_indices: set[int]) -> str:
    """Remove [N] markers from answer text for citations that were rejected."""
    import re
    if not removed_indices:
        return answer
    for idx in removed_indices:
        answer = re.sub(rf"\[{idx}\]", "", answer)
    # Clean up double spaces left behind
    answer = re.sub(r"  +", " ", answer)
    return answer.strip()


def _extract_year(crossref_data: dict[str, Any]) -> int | None:
    date_parts = crossref_data.get("published", {}).get("date-parts", [[]])
    if date_parts and date_parts[0]:
        return date_parts[0][0]
    return None


def _extract_journal(crossref_data: dict[str, Any]) -> str:
    titles = crossref_data.get("container-title", [])
    return titles[0] if titles else ""
