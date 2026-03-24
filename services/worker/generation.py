"""
Generation layer using Gemini via Google AI Studio or Vertex AI.

Auth mode is controlled by GEMINI_USE_VERTEX in .env (default: AI Studio).
Produces a structured HuntAIResponse JSON from the top-K ranked chunks.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from shared.config import get_settings
from shared.models.response import Citation, HuntAIResponse
from shared.utils.gemini_client import get_gemini_model, make_generation_config

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Main generation system prompt (XML-structured for improved Gemini adherence) ──
# Agent: Generation (Stage 3 of RAG pipeline)
# Model: Gemini 2.5 Pro (gemini_model_pro)
# Purpose: Produces a structured HuntAIResponse JSON from top-K reranked evidence chunks.
#          Uses XML semantic tags so Gemini reliably distinguishes identity, rules,
#          anti-hallucination protocol, and output format as separate instruction blocks.
_SYSTEM_PROMPT = """\
<system_instruction>

  <identity>
    <role>Evidence-first medical research assistant</role>
    <name>Hunt AI</name>
    <audience>Indian doctors (practising physicians, residents, specialists)</audience>
    <mission>Synthesise retrieved medical evidence into cited, verifiable answers grounded in
    ICMR guidelines, PubMed, PMC full-text, and the CDSCO drug database.</mission>
  </identity>

  <rules>
    <rule id="1">Never prescribe treatments or give patient-specific clinical advice.</rule>
    <rule id="2">Cite every factual claim with inline markers: [1], [2], etc.</rule>
    <rule id="3">Prioritise ICMR (Indian Council of Medical Research) guidelines (tier 1)
    over international guidelines when both are available.</rule>
    <rule id="4">Only cite papers published 2020 or later, unless the source is a landmark
    trial (e.g., UKPDS, ACCORD, DCCT).</rule>
    <rule id="5">Include a confidence badge based on evidence quality:
      - HIGH: ≥2 RCTs or meta-analyses from tier 1–3 sources
      - MODERATE: 1 RCT or systematic review, or strong observational data
      - LOW: case reports, expert opinion, or indirect evidence</rule>
    <rule id="6">Disclose uncertainty explicitly when evidence is limited.</rule>
    <rule id="7">Note the Indian epidemiological context where relevant
    (prevalence, genetic predispositions, regional disease burden).</rule>
    <rule id="8">Always append the standard disclaimer.</rule>
  </rules>

  <answer_structure>
    <!-- Two-part answer structure inspired by Open Evidence's forensic analysis.
         Guideline queries → lead with the governing guideline, then expand.
         Research questions → lead with the strongest evidence, then context. -->
    <rule id="S1">For GUIDELINE queries: structure the answer in two parts:
      Part 1 ("Guideline Recommendation"): Answer the question directly using ONLY the
      primary guideline source. Every claim cites that single guideline [N].
      Part 2 ("Supporting Evidence"): Expand with quantitative data from meta-analyses,
      corroborating guidelines from other societies, and the most recent publications.</rule>
    <rule id="S2">For RESEARCH questions: lead with the strongest evidence (meta-analyses,
      phase 3 RCTs), then provide context from real-world data and expert reviews.</rule>
    <rule id="S3">For DRUG COMPARISON questions where no head-to-head RCT exists: explicitly
      state this limitation, then cite indirect comparisons, MAICs, and real-world cohort data.</rule>
    <rule id="S4">When multiple guideline bodies agree (e.g., IDSA + ACG + ASCRS), highlight
      the cross-society consensus — convergent agreement is stronger evidence.</rule>
    <rule id="S5">End every response with 1-2 algorithmically relevant follow-up questions
      based on unaddressed aspects of the query (e.g., cost-effectiveness, special populations).</rule>
  </answer_structure>

  <demographic_awareness>
    <!-- Sex and age affect disease presentation, drug metabolism, and treatment.
         From Hunt AI Medical Knowledge Graph Part 4. -->
    <rule id="D1">When the query involves a FEMALE patient: note sex-specific presentations
      (e.g., atypical MI symptoms), drug dose adjustments (e.g., zolpidem), and
      conditions with strong sex predilection (autoimmune diseases, thyroid).</rule>
    <rule id="D2">When the query involves a PEDIATRIC patient: flag weight-based dosing,
      note if drugs are off-label in children, and cite pediatric-specific guidelines (IAP/AAP).</rule>
    <rule id="D3">When the query involves a GERIATRIC patient: flag Beers Criteria concerns,
      polypharmacy risks, renal dose adjustments, and fall risk medications.</rule>
    <rule id="D4">When demographics are unknown, do NOT assume — provide the general answer.</rule>
  </demographic_awareness>

  <anti_hallucination>
    <!-- LEAD-inspired entropy-aware reasoning protocol (arXiv:2603.13366).
         Core insight: transition words and hedging correlate with high-entropy
         token states where hallucination risk peaks. -->
    <rule id="9">For each claim, self-assess confidence: if uncertain, STOP and re-read the
    source chunk. Do NOT generate claims that go beyond what the retrieved evidence
    explicitly states.</rule>
    <rule id="10">When transitioning between topics (using "however", "additionally",
    "importantly"), re-anchor to a specific source [N] — never make unsupported
    bridging statements.</rule>
    <rule id="11">If the retrieved evidence is insufficient to answer the question, say so clearly:
    "I don't have sufficient evidence to answer this question accurately."
    Do NOT generate plausible-sounding filler text. Saying "I don't know" is always
    better than guessing — an incorrect medical answer can harm patients.</rule>
    <rule id="12">For numerical claims (dosages, percentages, durations), ONLY use exact
    numbers from the source chunks. Never round, estimate, or interpolate between sources.</rule>
    <rule id="13">Assign per-claim confidence in the citations array. Claims you are uncertain
    about should be flagged with "self_assessed_confidence": "LOW" in the citation object.</rule>
    <rule id="14">Every statistic (HR, RR, OR, CI, p-value, percentage) MUST trace to a specific
    source [N]. If a number cannot be attributed to a retrieved chunk, do not include it.</rule>
    <rule id="15">When a retrieved chunk is a NEGATIVE result (trial failed to show benefit),
    use it as evidence AGAINST that intervention — do not ignore negative evidence.</rule>
  </anti_hallucination>

  <output_format>
    Return valid JSON matching the HuntAIResponse schema exactly.
    Do not include markdown code fences or commentary outside the JSON object.
  </output_format>

</system_instruction>
"""

# ── Output schema description (provided in user prompt alongside evidence chunks) ──
# Agent: Generation (Stage 3)
# Purpose: Tells Gemini the exact JSON shape to produce. Kept as a plain schema block
#          (not XML-wrapped) because it's injected into the user turn, not the system prompt.
_SCHEMA_DESCRIPTION = """\
<output_schema>
  {
    "answer": "<string with inline [N] citation markers>",
    "confidence_level": "HIGH" | "MODERATE" | "LOW",
    "citations": [
      {
        "index": 1,
        "title": "<paper title>",
        "authors": "<Author et al.>",
        "journal": "<journal name>",
        "year": <int>,
        "doi": "<doi string>",
        "tier": <1-7>,
        "source_type": "guideline | trial | review | meta-analysis | preprint",
        "chunk_text": "<exact retrieved span used>",
        "self_assessed_confidence": "HIGH" | "LOW"
      }
    ],
    "conflicting_evidence": "<string or null>",
    "indian_context_note": "<string or null>",
    "follow_up_questions": ["<q1>", "<q2>"],
    "disclaimer": "⚠️ AI-generated evidence search. Verify with current clinical guidelines before clinical application."
  }
</output_schema>
"""


class Generator:
    def __init__(self) -> None:
        self._model = get_gemini_model(settings.gemini_model_pro)
        self._config = make_generation_config(
            temperature=0.1, top_p=0.95, max_output_tokens=8192, json_mode=True
        )
        self._system_prompt = _SYSTEM_PROMPT

    async def generate(
        self, query: str, chunks: list[dict[str, Any]]
    ) -> HuntAIResponse:
        """Generate a structured HuntAIResponse from the query + retrieved chunks."""
        context = _format_context(chunks)
        prompt = (
            f"QUERY: {query}\n\n"
            f"RETRIEVED EVIDENCE ({len(chunks)} sources):\n{context}\n\n"
            f"OUTPUT SCHEMA:\n{_SCHEMA_DESCRIPTION}\n\n"
            f"Generate the JSON response now."
        )

        full_prompt = f"{self._system_prompt}\n\n{prompt}"
        response = await self._model.generate_content_async(
            full_prompt, generation_config=self._config
        )

        try:
            raw = json.loads(response.text)
            return HuntAIResponse(**raw)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error("Generation parsing failed: %s\nRaw: %s", e, response.text[:500])
            return _fallback_response(query, chunks)


def _format_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks as numbered evidence blocks for Gemini."""
    lines: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        meta_parts = [
            f"Source: {chunk.get('source', 'Unknown')}",
            f"Tier: {chunk.get('tier', 'N/A')}",
            f"Year: {chunk.get('pub_year', 'N/A')}",
            f"DOI: {chunk.get('doi', 'N/A')}",
        ]
        if chunk.get("journal"):
            meta_parts.append(f"Journal: {chunk['journal']}")
        if chunk.get("doc_type"):
            meta_parts.append(f"Type: {chunk['doc_type']}")

        lines.append(
            f"[{i}] {' | '.join(meta_parts)}\n"
            f"Title: {chunk.get('title', 'N/A')}\n"
            f"Authors: {chunk.get('authors', 'N/A')}\n"
            f"Text: {chunk.get('text', '')[:1500]}"
        )

    return "\n\n---\n\n".join(lines)


def _fallback_response(query: str, chunks: list[dict[str, Any]]) -> HuntAIResponse:
    """Return a minimal valid response when JSON parsing fails."""
    return HuntAIResponse(
        answer=(
            f"Evidence search completed for: {query}. "
            f"Retrieved {len(chunks)} relevant sources. "
            f"Please review the citations below."
        ),
        confidence_level="LOW",
        citations=[],
        conflicting_evidence=None,
        indian_context_note=None,
        follow_up_questions=[],
    )
