---
name: whatsapp-ux-optimizer
description: >
  Design and optimize WhatsApp message UX for Noocyte AI. Use when designing
  response structure, message pacing, button placement, or multi-part message
  flows. Covers readability on small screens, citation formatting in plain text,
  interactive button strategy, and doctor engagement patterns.
argument-hint: "<response content to format>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# WhatsApp UX Optimizer

## Purpose

WhatsApp is not a web browser. It is a mobile messaging app used by Indian doctors on phones ranging from iPhone 15 Pro to budget Android devices. The UX decisions you make here directly affect whether a doctor trusts and uses Noocyte AI or abandons it after the first confusing response.

This skill goes beyond the technical formatting constraints (covered in `whatsapp-formatter`) and focuses on the **user experience design** — how to structure information so a busy doctor can act on it in 30 seconds.

---

## The Doctor's Context

Before designing any message, internalize this context:
- The doctor is likely between patients, not sitting at a desk
- They are reading on a 6-inch screen, often with one hand
- They need the answer in the first 3 lines, not buried at the end
- They will not scroll through 5 paragraphs to find the drug name
- They trust citations but do not have time to verify every one immediately
- They will share the response with colleagues if it's good

---

## The BLUF Principle (Bottom Line Up Front)

Every Noocyte AI response must lead with the answer, not the context.

```
❌ BAD STRUCTURE (OpenEvidence-style web format, wrong for WhatsApp):
"Clostridioides difficile infection (CDI) is a common healthcare-associated 
infection caused by... [3 paragraphs of background] ...therefore, according 
to IDSA/SHEA 2021 guidelines, fidaxomicin is preferred."

✅ GOOD STRUCTURE (WhatsApp BLUF format):
"*First-line CDI treatment:* Fidaxomicin 200mg BD × 10 days [1]

Lower recurrence vs vancomycin (16% vs 25%) [2]
Vancomycin acceptable if fidaxomicin unavailable.

[1] IDSA/SHEA CDI Guidelines 2021 (doi:10.1093/cid/ciab549)
[2] Liao et al., Pharmacotherapy 2022 (doi:10.1002/phar.2734)"
```

---

## Message Structure Templates

### Template 1: Drug/Treatment Query
```
*[Drug/Treatment Name]:* [Dose] [Route] [Duration] [N]

[Key differentiator or clinical pearl — 1 sentence]
[Alternative if first-line unavailable — 1 sentence]

[N] [Source name] [Year] (doi:[DOI])
[N] [Source name] [Year] (doi:[DOI])
```

### Template 2: Guideline Query
```
*[Guideline body] recommends:* [Recommendation] [N]

Strength: [Strong/Conditional] | Evidence: [High/Moderate/Low]
[India-specific note if applicable]

[N] [Guideline citation with DOI]
```

### Template 3: Comparison Query (e.g., Drug A vs Drug B)
```
*[Drug A] vs [Drug B] for [Condition]:*

Efficacy: [Comparable / A superior / B superior] [N]
Bleeding risk: [A lower / B lower / comparable] [N]
In CKD (eGFR 30-50): [Preferred agent and reason] [N]

Prefer [A/B] when: [Clinical scenario]

[N] [Citation with DOI]
```

### Template 4: Emergency Response (ALWAYS FIRST)
```
⚠️ *EMERGENCY — Call 108 immediately*

[Emergency guidance in 2 sentences max]

[Evidence-based next steps after stabilization]
```

---

## Citation Formatting for WhatsApp

WhatsApp does not render markdown tables or HTML. Citations must be in plain text:

```python
def format_citation_for_whatsapp(citation: dict, index: int) -> str:
    """
    Format a single citation for WhatsApp plain text display.
    
    WhatsApp renders: *bold*, _italic_, ~strikethrough~, ```code```
    WhatsApp does NOT render: # headers, | tables, [links](url), HTML
    """
    authors = citation.get("authors", "")
    # Truncate to first author + "et al." for space
    if "," in authors:
        first_author = authors.split(",")[0].strip()
        author_display = f"{first_author} et al."
    else:
        author_display = authors
    
    journal = citation.get("journal", "")
    year = citation.get("year", "")
    doi = citation.get("doi", "")
    
    if doi:
        return f"[{index}] {author_display}, {journal} {year} (doi:{doi})"
    else:
        return f"[{index}] {author_display}, {journal} {year}"

# Example output:
# [1] Johnson S et al., Clin Infect Dis 2021 (doi:10.1093/cid/ciab549)
# [2] Liao JX et al., Pharmacotherapy 2022 (doi:10.1002/phar.2734)
```

---

## Interactive Button Strategy

WhatsApp allows maximum 3 buttons per message. Use them strategically:

```python
BUTTON_STRATEGIES = {
    # Drug query: offer deeper drug info and alternatives
    "drug_lookup": [
        {"id": "drug_details", "title": "💊 Drug Details"},
        {"id": "alternatives", "title": "🔄 Alternatives"},
        {"id": "full_evidence", "title": "📋 Full Evidence"},
    ],
    
    # Guideline query: offer India-specific context
    "guideline": [
        {"id": "india_context", "title": "🇮🇳 India Context"},
        {"id": "full_evidence", "title": "📋 Full Evidence"},
        {"id": "related", "title": "🔄 Related Topics"},
    ],
    
    # Comparison query: offer head-to-head data
    "comparison": [
        {"id": "head_to_head", "title": "📊 Head-to-Head"},
        {"id": "full_evidence", "title": "📋 Full Evidence"},
        {"id": "india_context", "title": "🇮🇳 India Context"},
    ],
    
    # Emergency: NO buttons — doctor must call 108, not click buttons
    "emergency": [],
}
```

**Button Rules:**
- Never put buttons on Part 1 of a multi-part message — the doctor hasn't finished reading
- Never put buttons on an emergency response — remove friction, don't add it
- Button titles must be ≤ 20 characters (WhatsApp hard limit)
- Use emoji sparingly — one per button maximum

---

## Multi-Part Message Pacing

When a response must be split across multiple messages:

```python
MULTI_PART_RULES = {
    "split_at": 3800,  # chars — leave 296 char buffer below 4096 limit
    "delay_between_parts": 0.5,  # seconds — preserves message order
    "part_indicator": True,  # Show "Part 1/2" at start of each part
    "citations_on": "final_part",  # Never split citations across parts
    "buttons_on": "final_part",  # Buttons only on last message
    "summary_on": "first_part",  # BLUF answer always in Part 1
}

def format_part_indicator(part_num: int, total_parts: int) -> str:
    """Add part indicator to multi-part messages."""
    if total_parts == 1:
        return ""
    return f"_(Part {part_num}/{total_parts})_\n\n"
```

---

## The "Scannability" Test

Before any response is sent, run the scannability test:

```python
def scannability_test(message: str) -> dict:
    """
    Test if a WhatsApp message is scannable by a busy doctor.
    
    A scannable message:
    1. Has the key answer in the first 100 characters
    2. Has no paragraph longer than 3 lines
    3. Has citations clearly separated from the body
    4. Uses bold (*text*) for drug names and doses
    5. Has no more than 5 citations in the main body
    """
    lines = message.split("\n")
    
    issues = []
    
    # Check 1: Answer in first 100 chars
    if len(message) > 100 and not any(
        keyword in message[:100].lower() 
        for keyword in ["recommend", "preferred", "first-line", "guideline", "dose"]
    ):
        issues.append("Answer not in first 100 characters — apply BLUF principle")
    
    # Check 2: No paragraph > 3 lines
    current_para_len = 0
    for line in lines:
        if line.strip():
            current_para_len += 1
            if current_para_len > 3:
                issues.append(f"Paragraph too long (> 3 lines) — break it up")
                break
        else:
            current_para_len = 0
    
    # Check 3: Bold used for drug names
    import re
    drug_pattern = r'\b[A-Z][a-z]+(?:mab|nib|mide|statin|pril|sartan|olol)\b'
    drugs_found = re.findall(drug_pattern, message)
    unbolded_drugs = [d for d in drugs_found if f"*{d}*" not in message]
    if unbolded_drugs:
        issues.append(f"Drug names not bolded: {unbolded_drugs}")
    
    return {
        "passes": len(issues) == 0,
        "issues": issues,
        "char_count": len(message),
    }
```

---

## What NOT to Do

```
❌ Starting with background context before the answer
❌ Using markdown tables (| col1 | col2 |) — renders as plain text
❌ Using # headers — renders as literal # characters
❌ Putting all citations inline in the body (clutters reading)
❌ Sending buttons on Part 1 of a multi-part response
❌ Using more than 3 buttons
❌ Button titles > 20 characters ("📋 Full Evidence Report" is 24 chars — WRONG)
❌ Sending all parts simultaneously — WhatsApp may reorder them
❌ Omitting the India-specific context when it's available
```

---

## Testing This Skill

```python
# tests/unit/test_whatsapp_ux.py
from services.formatter.whatsapp_ux import scannability_test, format_citation_for_whatsapp

def test_bluf_passes_scannability():
    good_message = "*First-line CDI treatment:* Fidaxomicin 200mg BD × 10 days [1]\n\nLower recurrence vs vancomycin (16% vs 25%) [2]\n\n[1] Johnson et al., Clin Infect Dis 2021 (doi:10.1093/cid/ciab549)"
    result = scannability_test(good_message)
    assert result["passes"] is True

def test_citation_format():
    citation = {"authors": "Johnson S, Lavergne V", "journal": "Clin Infect Dis", "year": "2021", "doi": "10.1093/cid/ciab549"}
    formatted = format_citation_for_whatsapp(citation, 1)
    assert formatted == "[1] Johnson S et al., Clin Infect Dis 2021 (doi:10.1093/cid/ciab549)"
```

---

*A response that a doctor can't read in 30 seconds is a response they won't use.*
