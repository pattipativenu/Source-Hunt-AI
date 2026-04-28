---
name: indian-context-resolver
description: >
  Resolve Indian drug brand names to their International Nonproprietary Name
  (INN) and normalize Hinglish medical terms. Use internally to understand the
  doctor's query. NEVER include brand names in the final output. Ensures the
  system remains a transparent, brand-neutral clinical search engine.
argument-hint: "<text to resolve>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Indian Context Resolver

## Purpose

Indian doctors often refer to medications by their popular brand names (e.g., "Dolo", "Augmentin", "Pantocid"). As a transparent clinical search engine, Noocyte AI must understand these queries but **never promote or display brand names in its answers**.

This skill performs the internal "translation" from brand name to INN (generic name) so that the RAG pipeline can retrieve the correct evidence.

---

## The Rule of Absolute Brand Neutrality

> **INTERNAL USE ONLY:** Brand names are for query resolution and retrieval mapping.
> **OUTPUT PROHIBITION:** Brand names MUST NOT appear in the `answer` field of the JSON output. Only the INN (generic name) is permitted.

---

## Brand-to-INN Mapping (Internal Dictionary)

```python
BRAND_DICTIONARY = {
    # Antipyretics / Analgesics
    "dolo": "paracetamol",
    "calpol": "paracetamol",
    "crocin": "paracetamol",
    "combiflam": "ibuprofen + paracetamol",
    "voveran": "diclofenac",
    
    # Antibiotics
    "augmentin": "amoxicillin + clavulanate",
    "mox": "amoxicillin",
    "azithral": "azithromycin",
    "taxim": "cefotaxime",
    "ceftum": "cefuroxime",
    
    # Gastrointestinal
    "pantop": "pantoprazole",
    "pantocid": "pantoprazole",
    "pan": "pantoprazole",
    "digene": "antacid (magnesium/aluminium hydroxide)",
    
    # Cardiovascular
    "ecosprin": "aspirin",
    "telma": "telmisartan",
    "stamlo": "amlodipine",
    "jardiance": "empagliflozin",
    "forxiga": "dapagliflozin",
    
    # Endocrine
    "glycomet": "metformin",
    "thyronorm": "levothyroxine",
    "eltroxin": "levothyroxine",
    
    # Respiratory
    "asthalin": "salbutamol",
    "deriphyllin": "etofylline + theophylline",
}

def resolve_brands(text: str) -> str:
    """
    Internal function to replace brand names with INNs in the search query.
    This ensures the RAG pipeline finds evidence for the active ingredient.
    """
    normalized = text.lower()
    for brand, inn in BRAND_DICTIONARY.items():
        # Match brand name as a whole word
        normalized = re.sub(rf'\b{brand}\b', inn, normalized)
    return normalized
```

---

## Hinglish Normalization

Doctors may use Hinglish (Hindi + English) or common Indian medical slang. These must be normalized to standard clinical English for retrieval.

| Hinglish/Slang | Clinical English |
|----------------|------------------|
| "pet dard" | abdominal pain |
| "bukhar" | fever |
| "saans phoolna" | dyspnea / shortness of breath |
| "sugar" | diabetes mellitus / blood glucose |
| "BP" | blood pressure / hypertension |
| "loose motions" | diarrhea |
| "motions" | bowel movements |

---

## Integration in the Pipeline

```python
# Step 3: Indian Context Resolution
raw_query = "Dose of Dolo 650 for bukhar?"

# 1. Resolve brands internally
query_with_inn = resolve_brands(raw_query) 
# Result: "Dose of paracetamol 650 for bukhar?"

# 2. Normalize Hinglish internally
final_search_query = normalize_hinglish(query_with_inn)
# Result: "Dose of paracetamol 650 for fever?"

# 3. USE final_search_query for RAG and LLM Generation
# 4. LLM will generate answer using ONLY "paracetamol"
```

---

## Testing Brand Neutrality

```python
# tests/unit/test_brand_neutrality.py

def test_no_brands_in_output():
    query = "Is Augmentin better than Azithral for AECB?"
    response = noocyte_pipeline.run(query)
    
    # Prohibited brands
    prohibited = ["Augmentin", "Azithral", "Dolo", "Combiflam"]
    
    for brand in prohibited:
        assert brand not in response["answer"], f"Brand name {brand} found in output!"
    
    # Required INNs
    assert "amoxicillin" in response["answer"].lower()
    assert "azithromycin" in response["answer"].lower()
```

---

*We are a transparent clinical search engine. We provide evidence for molecules, not marketing for brands.*
