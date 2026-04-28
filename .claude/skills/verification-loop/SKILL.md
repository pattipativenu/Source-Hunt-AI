---
name: verification-loop
description: Use this skill when building or implementing verification loops — automated pipelines that generate, check, fix, and re-verify outputs until quality criteria are met. Also trigger for: iterative correction, automatic quality enforcement, self-healing pipelines, LLM output validation loops, assertion-based generation, retry-with-correction. Applies to any AI generation system where output quality must meet defined criteria.
---

# Verification Loop — Generate → Verify → Correct → Repeat

A verification loop is an automated quality enforcement system. Instead of generating once and hoping the output is correct, it generates, checks against defined criteria, fixes failures, and repeats until criteria are met or a retry limit is hit.

For medical AI specifically: the loop ensures citation alignment before anything reaches a doctor.

---

## The Core Pattern

```python
from dataclasses import dataclass
from typing import Callable, TypeVar, Any

T = TypeVar("T")

@dataclass
class VerificationResult:
    passed: bool
    score: float            # 0.0 to 1.0
    failures: list[str]     # Specific failure messages
    output: Any             # The verified (possibly corrected) output

async def verification_loop(
    generate: Callable[[], Any],          # Generate initial output
    verify: Callable[[Any], VerificationResult],  # Check output against criteria
    correct: Callable[[Any, list[str]], Any] | None = None,  # Fix failures
    max_attempts: int = 3,
    required_score: float = 0.8,
) -> VerificationResult:
    """
    Run generate → verify → correct loop until output meets criteria.
    
    Args:
        generate: Produces initial output
        verify: Returns VerificationResult with score and failure descriptions
        correct: Optional — given (output, failures), returns corrected output
        max_attempts: Maximum loop iterations
        required_score: Minimum passing score (0.0–1.0)
    
    Returns: Best VerificationResult achieved within max_attempts
    """
    best_result = None
    output = await generate()
    
    for attempt in range(max_attempts):
        result = await verify(output)
        
        log.info(
            "Verification loop attempt %d/%d: score=%.2f passed=%s failures=%d",
            attempt + 1, max_attempts, result.score, result.passed, len(result.failures),
        )
        
        # Keep best result regardless
        if best_result is None or result.score > best_result.score:
            best_result = result
        
        if result.passed:
            return result
        
        # Final attempt — return best we got
        if attempt == max_attempts - 1:
            log.warning("Verification loop exhausted %d attempts, best score: %.2f", max_attempts, best_result.score)
            return best_result
        
        # Attempt correction if corrector provided
        if correct and result.failures:
            output = await correct(output, result.failures)
        else:
            # Re-generate if no corrector
            output = await generate()
    
    return best_result
```

---

## Medical Citation Verification Loop

The most critical application in Noocyte: verify that every claim in a generated medical response is supported by its cited source.

```python
async def medical_response_verification_loop(
    query: str,
    retrieved_chunks: list[dict],
    gemini_model,
    max_attempts: int = 2,  # 2 is usually enough; 3+ is diminishing returns
) -> dict:
    """
    Generate → verify citations → correct if needed → verify again.
    """
    
    async def generate() -> dict:
        return await generate_medical_response(query, retrieved_chunks, gemini_model)
    
    async def verify(response: dict) -> VerificationResult:
        failures = []
        
        # 1. Citation alignment check
        inline = set(re.findall(r"\[(\d+)\]", response.get("answer", "")))
        refs = {str(r["id"]) for r in response.get("references", [])}
        orphaned = inline - refs
        if orphaned:
            failures.append(f"Orphaned citations (no reference entry): {orphaned}")
        
        # 2. Prescriptive language check
        prescriptive = [
            p for p in ["prescribe", "administer", "give the patient", "start on", "initiate"]
            if p in response.get("answer", "").lower()
        ]
        if prescriptive:
            failures.append(f"Prescriptive language detected: {prescriptive}")
        
        # 3. NLI entailment for statistical claims
        verified_claims = await verify_all_citations(
            response.get("claims", []),
            retrieved_chunks,
            gemini_model,
            threshold=0.7,
        )
        
        failed_nli = [c for c in verified_claims if not c.passes]
        if failed_nli:
            for c in failed_nli:
                failures.append(f"Unsupported claim ({c.confidence:.2f}): {c.claim_text[:60]}...")
        
        # 4. Minimum citation count
        if len(inline) < 2:
            failures.append(f"Insufficient citations: {len(inline)} found, need ≥ 2")
        
        # Scoring
        total_checks = 4
        passed_checks = sum([
            len(orphaned) == 0,
            len(prescriptive) == 0,
            len(failed_nli) == 0,
            len(inline) >= 2,
        ])
        score = passed_checks / total_checks
        
        return VerificationResult(
            passed=score >= 0.8 and len(orphaned) == 0 and len(prescriptive) == 0,
            score=score,
            failures=failures,
            output=response,
        )
    
    async def correct(response: dict, failures: list[str]) -> dict:
        """Ask LLM to fix specific failures."""
        correction_prompt = f"""
The medical evidence response has the following problems:
{chr(10).join(f"- {f}" for f in failures)}

Original response:
{response["answer"]}

Fix ONLY the listed problems. Keep everything else identical.
Return corrected JSON with same schema.
"""
        corrected_text = await gemini_model.generate_content_async(
            correction_prompt,
            generation_config={"temperature": 0.0, "response_mime_type": "application/json"},
        )
        try:
            return json.loads(corrected_text.text)
        except json.JSONDecodeError:
            return response  # Correction failed — return original
    
    result = await verification_loop(
        generate=generate,
        verify=verify,
        correct=correct,
        max_attempts=max_attempts,
        required_score=0.8,
    )
    
    return result.output
```

---

## Assertion-Based Generation

For structured outputs where the schema is well-defined, add assertion checks before verification:

```python
def assert_response_structure(response: dict) -> list[str]:
    """
    Fast structural assertions — run before expensive NLI verification.
    Return list of structural failures.
    """
    failures = []
    
    required_fields = ["answer", "clinical_bottom_line", "evidence_quality", "claims", "references"]
    for field in required_fields:
        if field not in response:
            failures.append(f"Missing required field: {field}")
    
    if "references" in response and "answer" in response:
        ref_ids = {r["id"] for r in response["references"]}
        inline_ids = {int(n) for n in re.findall(r"\[(\d+)\]", response["answer"])}
        
        orphaned = inline_ids - ref_ids
        if orphaned:
            failures.append(f"Inline citations without reference entry: {orphaned}")
        
        unused = ref_ids - inline_ids
        if unused:
            failures.append(f"References never cited in answer: {unused}")
    
    if "evidence_quality" in response:
        valid_quality = {"high", "moderate", "low", "insufficient"}
        if response["evidence_quality"] not in valid_quality:
            failures.append(f"Invalid evidence_quality: {response['evidence_quality']}")
    
    return failures
```

---

## Practical Guidance

### When to Loop vs When to Accept

```python
# Case 1: Perfect first attempt — common for simple drug lookup queries
result_attempt_1 = verify(output)
if result_attempt_1.passed:
    return output  # Don't waste API calls on correction

# Case 2: Structural failures (orphaned citations) — correct and retry
if orphaned_citations in failures:
    corrected = correct(output, failures)
    return verify(corrected)

# Case 3: NLI failures — remove unsupported claims rather than re-generating
if nli_failures in failures:
    cleaned = remove_unsupported_claims(output, nli_failures)
    return cleaned  # Cleaning is cheaper than re-generation

# Case 4: Fundamental failures (missing required fields) — re-generate
output = await generate()
```

### Cost Implications

Each verification loop iteration costs:
- One Gemini generation: ~$0.001 per query (Flash)
- NLI verification: ~$0.0005 per claim × N claims
- Total per iteration: ~$0.002-$0.005

For medical content, 2 iterations (initial + one correction) is the right tradeoff. Three iterations is rarely justified — if the pipeline is failing consistently, fix the prompt or retrieval, not the loop count.

### Anti-Patterns

```python
# ❌ Unbounded loop — can run forever
while not verify(output).passed:
    output = generate()

# ❌ Trusting "correction" without re-verification
output = correct(output, failures)
return output  # Did the correction actually fix anything?

# ❌ Re-generating when removing content is cheaper
output = generate()  # Expensive; loses good parts of original
# Better: remove the failing claim, keep the rest

# ❌ Ignoring loop cost at scale
# 1000 queries/day × 2 iterations × $0.003 = $6/day = $180/month extra
# Only loop when the cost of a bad output > cost of the loop
```
