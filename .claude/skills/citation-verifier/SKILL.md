---
name: citation-verifier
description: Use this skill when building or debugging post-generation citation verification in RAG systems — including claim decomposition, NLI entailment checking, citation correction, confidence scoring, and the complete P-Cite pipeline. Also trigger for: hallucinated citations, citation alignment bugs, "does the cited source support this claim", LLM-as-judge verification, MiniCheck, AlignScore. Applies to any domain where citation accuracy is critical.
---

# Citation Verifier — The Post-Generation Verification Pipeline

RAG systems without post-generation verification have ~74% citation accuracy. That means 1 in 4 citations either doesn't exist, doesn't support the claim, or points to a different claim. For medical AI, this is unacceptable.

The P-Cite (Post-hoc Citation) pipeline verifies every claim after generation, before delivery.

---

## The Four-Stage Pipeline

```
Generated Answer (inline [N] citations)
  ↓
Stage 1: Claim Decomposition
  → Split answer into atomic sentences
  → Extract [N] markers from each sentence
  → Create (claim_text, source_passage) pairs
  ↓
Stage 2: NLI Entailment Check
  → Score each (claim, source) pair: confidence 0.0–1.0
  → Medical threshold: > 0.7 (not standard 0.5)
  ↓
Stage 3: Citation Correction
  → For failed pairs: search all retrieved chunks for a better source
  → If found: reassign citation to correct source
  → If not found: mark claim as "unsupported"
  ↓
Stage 4: Delivery Decision
  → All supported: deliver as-is
  → Some unsupported: remove unsupported claims, add disclaimer
  → Critical claim unsupported: flag for review, deliver with warning
```

---

## Implementation

### Stage 1: Claim Decomposition

```python
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClaimCitationPair:
    sentence_index: int
    claim_text: str
    citation_ids: list[int]  # The [N] numbers extracted from this sentence
    source_passages: list[str]  # The actual text of the cited sources

def decompose_answer_into_claims(
    answer: str,
    references: list[dict],
) -> list[ClaimCitationPair]:
    """
    Split answer into atomic sentences and extract citation markers.
    
    Input:  "Fidaxomicin is preferred for CDI [1]. It reduces recurrence [2][3]."
    Output: [
        ClaimCitationPair(claim="Fidaxomicin is preferred for CDI", citation_ids=[1], ...),
        ClaimCitationPair(claim="It reduces recurrence", citation_ids=[2, 3], ...),
    ]
    """
    # Split on sentence boundaries (simple approach — use spaCy for production)
    sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
    
    ref_map = {r["id"]: r.get("content", "") for r in references}
    
    pairs = []
    for i, sentence in enumerate(sentences):
        # Extract all [N] markers from this sentence
        citation_ids = [int(n) for n in re.findall(r'\[(\d+)\]', sentence)]
        
        # Remove citation markers for clean claim text
        clean_claim = re.sub(r'\[\d+\]', '', sentence).strip()
        
        if not clean_claim or not citation_ids:
            continue  # Skip uncited sentences (intro/conclusion phrases)
        
        source_passages = [
            ref_map.get(cid, "")
            for cid in citation_ids
            if cid in ref_map
        ]
        
        pairs.append(ClaimCitationPair(
            sentence_index=i,
            claim_text=clean_claim,
            citation_ids=citation_ids,
            source_passages=source_passages,
        ))
    
    return pairs
```

### Stage 2: NLI Entailment Check (Gemini-as-Judge for MVP)

```python
import json
import google.generativeai as genai

ENTAILMENT_PROMPT = """\
You are verifying whether a source passage supports a medical claim.

SOURCE PASSAGE:
\"\"\"{source}\"\"\"

CLAIM:
\"\"\"{claim}\"\"\"

Question: Does the source passage directly support this specific claim?
Consider:
1. Is the KEY FACT (statistic, recommendation, mechanism) in the source?
2. Is the attribution correct (e.g., claim says "IDSA recommends" — does source confirm this is from IDSA)?
3. Is the claim more specific than the source allows (hallucinated precision)?

Return valid JSON only:
{{
    "entailment": true or false,
    "confidence": 0.0 to 1.0,
    "reason": "one sentence explaining the decision"
}}"""

async def check_entailment(
    claim: str,
    source_passage: str,
    model: genai.GenerativeModel,
    threshold: float = 0.7,
) -> dict:
    """
    Use Gemini as judge to verify claim-source entailment.
    
    Threshold 0.7 for medical content (vs standard 0.5) reduces false positives.
    """
    prompt = ENTAILMENT_PROMPT.format(
        source=source_passage[:2000],  # Cap to avoid token waste
        claim=claim[:500],
    )
    
    response = await model.generate_content_async(
        contents=prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.0,
            response_mime_type="application/json",
        ),
    )
    
    try:
        result = json.loads(response.text)
    except json.JSONDecodeError:
        # LLM returned invalid JSON — conservative: fail the claim
        return {"entailment": False, "confidence": 0.0, "reason": "Verification failed"}
    
    result["passes"] = result.get("confidence", 0.0) >= threshold
    return result
```

### Stage 3: Full Verification with Correction

```python
@dataclass
class VerifiedClaim:
    claim_text: str
    citation_ids: list[int]
    confidence: float
    passes: bool
    corrected: bool = False  # True if citation was reassigned
    reason: str = ""

async def verify_all_claims(
    claims: list[ClaimCitationPair],
    all_retrieved_chunks: list[dict],
    model: genai.GenerativeModel,
    threshold: float = 0.7,
) -> list[VerifiedClaim]:
    """
    Verify each claim and attempt correction on failures.
    """
    verified = []
    
    for claim_pair in claims:
        best_confidence = 0.0
        best_source_idx = 0
        corrected = False
        
        # Check each cited source
        for i, source in enumerate(claim_pair.source_passages):
            if not source:
                continue
            result = await check_entailment(claim_pair.claim_text, source, model, threshold)
            
            if result.get("confidence", 0) > best_confidence:
                best_confidence = result["confidence"]
                best_source_idx = i
        
        # If primary citation fails, try all retrieved chunks
        if best_confidence < threshold:
            for chunk in all_retrieved_chunks:
                content = chunk.get("content", "")
                if not content:
                    continue
                result = await check_entailment(claim_pair.claim_text, content, model, threshold)
                
                if result.get("confidence", 0) > best_confidence:
                    best_confidence = result["confidence"]
                    corrected = True
        
        verified.append(VerifiedClaim(
            claim_text=claim_pair.claim_text,
            citation_ids=claim_pair.citation_ids,
            confidence=best_confidence,
            passes=best_confidence >= threshold,
            corrected=corrected,
            reason=f"Best confidence: {best_confidence:.2f}",
        ))
    
    return verified
```

### Stage 4: Delivery Decision

```python
def apply_verification(
    original_answer: str,
    verified_claims: list[VerifiedClaim],
    min_pass_rate: float = 0.85,
) -> dict:
    """
    Modify answer based on verification results.
    Returns cleaned answer and metadata.
    """
    failed = [c for c in verified_claims if not c.passes]
    pass_rate = 1 - (len(failed) / len(verified_claims)) if verified_claims else 1.0
    
    answer = original_answer
    warnings = []
    
    # Remove sentences with failed citations
    for failed_claim in failed:
        # Find and remove the sentence containing this claim
        # (simplified — production should use sentence tokenisation)
        sentences = answer.split(". ")
        answer = ". ".join(
            s for s in sentences
            if failed_claim.claim_text[:30] not in s  # Approximate match
        )
        warnings.append(f"Removed unverified claim: {failed_claim.claim_text[:50]}...")
    
    # Add disclaimer if many claims failed
    if pass_rate < min_pass_rate:
        answer += "\n\n⚠️ *Note: Some claims could not be fully verified against indexed sources. Please consult original guidelines directly.*"
    
    return {
        "answer": answer,
        "pass_rate": pass_rate,
        "verified_claim_count": len(verified_claims),
        "failed_claim_count": len(failed),
        "warnings": warnings,
        "avg_confidence": sum(c.confidence for c in verified_claims) / len(verified_claims) if verified_claims else 0,
    }
```

---

## DOI Validation (Citation Existence Check)

Before any citation reaches the doctor, validate the DOI exists:

```python
import httpx

async def validate_doi(
    doi: str,
    client: httpx.AsyncClient,
    email: str,
) -> bool:
    """
    Returns True if DOI resolves to a real paper.
    A False here means the citation is hallucinated.
    """
    if not doi:
        return False
    
    url = f"https://api.crossref.org/works/{doi}"
    try:
        response = await client.get(
            url,
            params={"mailto": email},  # Polite Pool: higher rate limit
            timeout=5.0,
        )
        return response.status_code == 200
    except (httpx.TimeoutException, httpx.ConnectError):
        return True  # Network failure — don't penalise valid DOIs
```

---

## Common Mistakes

```python
# ❌ Verifying at the document level instead of the sentence level
# "The paper supports the answer" is not the same as "this sentence is supported"

# ❌ Using 0.5 threshold for medical content
# Standard NLI threshold → too many false positives in medical claims

# ❌ Removing all uncited sentences (drops intro and conclusion context)
# Only remove sentences with FAILED citations, not sentences without citations

# ❌ Not logging verification failures
# You can't improve what you don't measure
log.info("Citation verification", extra={
    "query_id": query_id,
    "total_claims": len(verified_claims),
    "failed_claims": len([c for c in verified_claims if not c.passes]),
    "avg_confidence": avg_confidence,
})
```
