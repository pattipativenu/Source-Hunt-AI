---
name: indian-context-resolver
description: >
  Resolve Indian medical context before any retrieval or generation step.
  Use when a query contains Indian drug brand names, Hinglish phrases, regional
  medical terminology, or references to Indian guidelines (ICMR, NMC, CDSCO).
  Handles brand-to-generic (INN) resolution, Hinglish normalization, and
  India-specific regulatory context injection.
argument-hint: "<raw query text>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Indian Context Resolver

## Purpose

This skill ensures that every query is correctly understood in the Indian medical context before it reaches the RAG pipeline. It performs three operations in sequence:

1. **Brand-to-INN Resolution** — Converts Indian drug brand names to International Nonproprietary Names (INN) so PubMed searches return relevant results.
2. **Hinglish Normalization** — Detects and normalizes Hindi-English code-switched queries into standard medical English.
3. **India Context Injection** — Appends India-specific context flags (e.g., `india_context=True`, `prefer_icmr=True`) to the query metadata so the retrieval pipeline prioritizes Indian sources.

---

## Sub-Skills

This skill has three sub-skills that can be used independently:

- **`brand-resolver`** — Brand name to INN lookup only
- **`hinglish-normalizer`** — Language normalization only
- **`icmr-context-injector`** — Source priority flagging only

---

## When to Use

Trigger this skill **before** calling `medical-evidence-retrieval` or `ncbi-pubmed` whenever:
- The query contains a capitalized word that looks like a brand name (Dolo, Augmentin, Glycomet)
- The query contains Hindi words or transliterated Hindi (bukhar, dard, suger, BP)
- The query explicitly mentions Indian context ("in India", "ICMR", "Indian patient")
- The query contains Indian-specific dosing conventions (e.g., "BD", "TDS", "OD" — common in Indian prescriptions)

---

## Sub-Skill 1: Brand-to-INN Resolution

### The Core Dictionary (Expand This Continuously)

```python
# shared/data/indian_brand_dict.py
"""
Indian Drug Brand → INN Resolution Dictionary
Sources: CDSCO drug database, NPPA price list, common Indian formularies
Last updated: 2026-01
"""

INDIAN_BRAND_TO_INN: dict[str, dict] = {
    # Analgesics / Antipyretics
    "dolo": {"inn": "paracetamol", "strengths": ["500mg", "650mg"], "class": "analgesic"},
    "dolo 650": {"inn": "paracetamol 650mg", "strengths": ["650mg"], "class": "analgesic"},
    "calpol": {"inn": "paracetamol", "strengths": ["125mg", "250mg", "500mg"], "class": "analgesic", "note": "paediatric"},
    "combiflam": {"inn": "ibuprofen + paracetamol", "strengths": ["400mg+325mg"], "class": "analgesic"},
    "brufen": {"inn": "ibuprofen", "strengths": ["200mg", "400mg", "600mg"], "class": "nsaid"},
    "voveran": {"inn": "diclofenac", "strengths": ["50mg", "75mg"], "class": "nsaid"},

    # Antibiotics
    "augmentin": {"inn": "amoxicillin + clavulanate", "strengths": ["625mg", "1.2g IV"], "class": "penicillin"},
    "ciplox": {"inn": "ciprofloxacin", "strengths": ["250mg", "500mg", "750mg"], "class": "fluoroquinolone"},
    "azithral": {"inn": "azithromycin", "strengths": ["250mg", "500mg"], "class": "macrolide"},
    "zithromax": {"inn": "azithromycin", "strengths": ["250mg", "500mg"], "class": "macrolide"},
    "taxim": {"inn": "cefotaxime", "strengths": ["250mg", "500mg", "1g IV"], "class": "cephalosporin"},
    "monocef": {"inn": "ceftriaxone", "strengths": ["250mg", "500mg", "1g IV"], "class": "cephalosporin"},
    "meronem": {"inn": "meropenem", "strengths": ["500mg IV", "1g IV"], "class": "carbapenem"},

    # Cardiovascular
    "ecosprin": {"inn": "aspirin", "strengths": ["75mg", "150mg"], "class": "antiplatelet"},
    "telma": {"inn": "telmisartan", "strengths": ["20mg", "40mg", "80mg"], "class": "arb"},
    "amlodac": {"inn": "amlodipine", "strengths": ["2.5mg", "5mg", "10mg"], "class": "ccb"},
    "metpure": {"inn": "metoprolol succinate", "strengths": ["25mg", "50mg"], "class": "beta-blocker"},
    "atorva": {"inn": "atorvastatin", "strengths": ["10mg", "20mg", "40mg", "80mg"], "class": "statin"},
    "rozavel": {"inn": "rosuvastatin", "strengths": ["5mg", "10mg", "20mg"], "class": "statin"},

    # Diabetes
    "glycomet": {"inn": "metformin", "strengths": ["500mg", "850mg", "1000mg"], "class": "biguanide"},
    "glucophage": {"inn": "metformin", "strengths": ["500mg", "850mg", "1000mg"], "class": "biguanide"},
    "januvia": {"inn": "sitagliptin", "strengths": ["25mg", "50mg", "100mg"], "class": "dpp4-inhibitor"},
    "jardiance": {"inn": "empagliflozin", "strengths": ["10mg", "25mg"], "class": "sglt2-inhibitor"},
    "forxiga": {"inn": "dapagliflozin", "strengths": ["5mg", "10mg"], "class": "sglt2-inhibitor"},
    "glynase": {"inn": "glipizide", "strengths": ["2.5mg", "5mg"], "class": "sulfonylurea"},
    "amaryl": {"inn": "glimepiride", "strengths": ["1mg", "2mg", "3mg", "4mg"], "class": "sulfonylurea"},

    # GI / Acid Suppression
    "pantop": {"inn": "pantoprazole", "strengths": ["20mg", "40mg"], "class": "ppi"},
    "pan": {"inn": "pantoprazole", "strengths": ["40mg"], "class": "ppi"},
    "omez": {"inn": "omeprazole", "strengths": ["10mg", "20mg", "40mg"], "class": "ppi"},
    "nexpro": {"inn": "esomeprazole", "strengths": ["20mg", "40mg"], "class": "ppi"},

    # Thyroid
    "thyronorm": {"inn": "levothyroxine", "strengths": ["12.5mcg", "25mcg", "50mcg", "75mcg", "100mcg"], "class": "thyroid-hormone"},
    "eltroxin": {"inn": "levothyroxine", "strengths": ["25mcg", "50mcg", "100mcg"], "class": "thyroid-hormone"},

    # Respiratory
    "asthalin": {"inn": "salbutamol", "strengths": ["2mg", "4mg", "100mcg inhaler"], "class": "saba"},
    "seroflo": {"inn": "salmeterol + fluticasone", "strengths": ["25/125", "25/250", "50/250", "50/500"], "class": "laba-ics"},
    "foracort": {"inn": "formoterol + budesonide", "strengths": ["6/100", "6/200", "12/400"], "class": "laba-ics"},

    # Anticoagulants
    "xarelto": {"inn": "rivaroxaban", "strengths": ["10mg", "15mg", "20mg"], "class": "doac"},
    "eliquis": {"inn": "apixaban", "strengths": ["2.5mg", "5mg"], "class": "doac"},
    "pradaxa": {"inn": "dabigatran", "strengths": ["75mg", "110mg", "150mg"], "class": "doac"},
    "acitrom": {"inn": "acenocoumarol", "strengths": ["1mg", "2mg", "4mg"], "class": "vka", "note": "Indian alternative to warfarin"},
}

def resolve_brand_to_inn(query: str) -> tuple[str, dict | None]:
    """
    Resolve Indian drug brand names in a query to INN.
    
    Returns:
        tuple: (resolved_query, resolution_metadata)
        resolution_metadata contains the brand found, INN used, and drug class
    
    Example:
        resolve_brand_to_inn("Dolo 650 for fever in adults")
        → ("paracetamol 650mg for fever in adults", {"brand": "dolo 650", "inn": "paracetamol 650mg", "class": "analgesic"})
    """
    query_lower = query.lower()
    
    # Try multi-word brands first (e.g., "Dolo 650" before "Dolo")
    for brand, data in sorted(INDIAN_BRAND_TO_INN.items(), key=lambda x: len(x[0]), reverse=True):
        if brand in query_lower:
            resolved_query = query_lower.replace(brand, data["inn"])
            return resolved_query, {"brand": brand, **data}
    
    return query, None
```

---

## Sub-Skill 2: Hinglish Normalizer

```python
# shared/utils/hinglish_normalizer.py
"""
Normalize Hinglish (Hindi-English code-switched) medical queries to standard English.
Common patterns in Indian medical WhatsApp groups.
"""

HINGLISH_MEDICAL_PATTERNS: dict[str, str] = {
    # Symptoms in Hindi/Hinglish
    "bukhar": "fever",
    "bukhaar": "fever",
    "dard": "pain",
    "sir dard": "headache",
    "pet dard": "abdominal pain",
    "seene mein dard": "chest pain",
    "sans lene mein takleef": "difficulty breathing",
    "chakkar": "dizziness",
    "ulti": "vomiting",
    "dast": "diarrhea",
    "khasi": "cough",
    "nazla": "nasal congestion",
    
    # Conditions
    "suger": "diabetes",
    "sugar": "diabetes",  # common misspelling
    "madhumeh": "diabetes",
    "bp": "hypertension",
    "high bp": "hypertension",
    "thyroid": "hypothyroidism",  # context-dependent
    "heart ki problem": "cardiac condition",
    "kidney ki problem": "renal condition",
    
    # Dosing conventions (Indian prescription abbreviations)
    " od ": " once daily ",
    " bd ": " twice daily ",
    " tds ": " three times daily ",
    " qid ": " four times daily ",
    " sos ": " as needed ",
    " hs ": " at bedtime ",
    " ac ": " before meals ",
    " pc ": " after meals ",
    
    # Common phrases
    "kya dena chahiye": "what should be given",
    "kya treatment hai": "what is the treatment",
    "kitna dose": "what is the dose",
    "side effects kya hain": "what are the side effects",
    "patient ko": "for the patient",
    "sir one of my patients": "",  # Remove polite preamble
    "dear sir": "",
    "respected sir": "",
}

def normalize_hinglish(query: str) -> tuple[str, bool]:
    """
    Normalize Hinglish medical query to standard English.
    
    Returns:
        tuple: (normalized_query, was_hinglish)
    """
    normalized = query.lower()
    was_hinglish = False
    
    for hinglish, english in HINGLISH_MEDICAL_PATTERNS.items():
        if hinglish in normalized:
            normalized = normalized.replace(hinglish, english)
            was_hinglish = True
    
    return normalized.strip(), was_hinglish
```

---

## Sub-Skill 3: ICMR Context Injector

```python
# shared/utils/icmr_context_injector.py
"""
Inject India-specific context flags into query metadata.
These flags control source priority in the retrieval pipeline.
"""

INDIA_SPECIFIC_CONDITIONS = {
    # Conditions with India-specific guidelines
    "tuberculosis", "tb", "mdr-tb", "xdr-tb",
    "malaria", "dengue", "typhoid", "leptospirosis",
    "kala azar", "visceral leishmaniasis",
    "snakebite", "snake bite",
    "covid", "covid-19", "sars-cov-2",
    "diabetes", "t2dm", "type 2 diabetes",
    "hypertension", "high bp",
    "anemia", "anaemia", "iron deficiency",
    "vitamin d deficiency",
    "hypothyroidism",
}

def inject_india_context(query: str, metadata: dict) -> dict:
    """
    Add India-specific context flags to query metadata.
    
    These flags are consumed by the retrieval pipeline to:
    1. Boost ICMR and Indian guideline chunks in ranking
    2. Add India-specific drug availability context
    3. Include Indian pricing information for drug recommendations
    """
    query_lower = query.lower()
    
    # Check if query is about an India-specific condition
    is_india_specific = any(cond in query_lower for cond in INDIA_SPECIFIC_CONDITIONS)
    
    # Check for explicit India references
    has_india_reference = any(term in query_lower for term in [
        "india", "indian", "icmr", "nmc", "cdsco", "mohfw",
        "rupee", "₹", "hindi", "regional"
    ])
    
    metadata.update({
        "india_context": is_india_specific or has_india_reference,
        "prefer_icmr": is_india_specific,
        "include_drug_pricing": True,  # Always include Indian pricing
        "drug_availability_check": True,  # Check if drug is available in India
    })
    
    return metadata
```

---

## Complete Pipeline Integration

```python
# services/worker/query_understanding.py
async def understand(self, raw_query: str) -> dict:
    """Full query understanding pipeline with Indian context resolution."""
    
    # Step 1: Emergency check (ALWAYS FIRST)
    emergency = check_emergency_keywords(raw_query)
    if emergency.is_emergency:
        return {"is_emergency": True, "emergency_message": emergency.message}
    
    # Step 2: PII redaction
    clean_query = redact_pii(raw_query)
    
    # Step 3: Hinglish normalization
    normalized_query, was_hinglish = normalize_hinglish(clean_query)
    
    # Step 4: Brand-to-INN resolution
    resolved_query, brand_metadata = resolve_brand_to_inn(normalized_query)
    
    # Step 5: PICO extraction (using Gemini)
    pico = await extract_pico(resolved_query)
    
    # Step 6: Intent classification
    intent = await classify_intent(resolved_query)
    
    # Step 7: India context injection
    metadata = inject_india_context(resolved_query, {
        "original_query": raw_query,
        "was_hinglish": was_hinglish,
        "brand_resolved": brand_metadata,
        "intent": intent,
        "pico": pico,
    })
    
    return {
        "translated_query": resolved_query,
        "is_emergency": False,
        **metadata,
    }
```

---

## What NOT to Do

```python
# ❌ Running PubMed search with brand names
results = await pubmed.search("Dolo 650 fever treatment")
# PubMed returns 0 results — "Dolo 650" is not indexed

# ❌ Ignoring Hinglish — passing raw query to Gemini
response = await gemini.generate("bukhar mein kya dena chahiye")
# Gemini may respond in Hindi, breaking the structured JSON schema

# ❌ Skipping India context injection
chunks = await qdrant.search(query)  # No India boost
# Returns US/European guidelines first, ICMR buried at position 8

# ✅ Always run the full Indian context resolution pipeline first
understood = await query_understanding.understand(raw_query)
chunks = await retriever.retrieve(understood)  # Now India-aware
```

---

## Testing This Skill

```python
# tests/unit/test_indian_context_resolver.py
import pytest
from shared.data.indian_brand_dict import resolve_brand_to_inn
from shared.utils.hinglish_normalizer import normalize_hinglish
from shared.utils.icmr_context_injector import inject_india_context

class TestBrandResolution:
    def test_dolo_650_resolves(self):
        result, meta = resolve_brand_to_inn("Dolo 650 for fever")
        assert "paracetamol" in result.lower()
        assert meta["brand"] == "dolo 650"

    def test_augmentin_resolves(self):
        result, meta = resolve_brand_to_inn("Augmentin 625 for URTI")
        assert "amoxicillin" in result.lower()
        assert "clavulanate" in result.lower()

    def test_no_brand_returns_original(self):
        result, meta = resolve_brand_to_inn("What is the treatment for CDI?")
        assert result == "What is the treatment for CDI?"
        assert meta is None

class TestHinglishNormalizer:
    def test_bukhar_normalized(self):
        result, was_hinglish = normalize_hinglish("patient ko bukhar hai")
        assert "fever" in result
        assert was_hinglish is True

    def test_bd_dosing_normalized(self):
        result, _ = normalize_hinglish("give metformin 500mg BD")
        assert "twice daily" in result

class TestIndiaContextInjector:
    def test_tb_gets_icmr_flag(self):
        meta = inject_india_context("MDR-TB treatment in India", {})
        assert meta["prefer_icmr"] is True
        assert meta["india_context"] is True
```

---

*Every Indian doctor deserves answers in their context, not a translation of someone else's.*
