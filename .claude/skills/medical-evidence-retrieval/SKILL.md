---
name: medical-evidence-retrieval
description: Use this skill when building, debugging, or extending the medical evidence retrieval pipeline — including source priority routing (ICMR > international guidelines > journals), specialty-specific journal targeting, drug brand-to-generic resolution for Indian medicines, PICO query construction for clinical questions, multi-source parallel retrieval orchestration, and evidence tier classification. Also trigger for: ICMR guidelines, Indian drug formulary, clinical evidence synthesis, PubMed MeSH for medical specialties, evidence hierarchy in medicine. Applies to any clinical decision support system.
---

# Medical Evidence Retrieval — Domain-Specific Orchestration

This skill covers the intersection of clinical medicine and information retrieval: how to find the right medical evidence for a clinical question, from the right sources, in the right order.

## The Core Problem

A query like "first-line treatment for CDI in adults" could retrieve:
- A 2012 rat model of C. difficile (wrong species)
- A 2019 case report from a single centre (wrong evidence tier)
- A 2021 IDSA/SHEA guideline (correct)
- A 2022 meta-analysis quantifying recurrence rates (correct and quantitative)
- A 2025 JAMA review validating the 2021 recommendation (correct and recent)

The retrieval pipeline must find the 2021 guideline AND the 2022 meta-analysis AND the 2025 update — not the rat study or the case report.

---

## PICO Query Construction

Every clinical question maps to PICO (Population, Intervention, Comparison, Outcome). Decomposing the query before retrieval dramatically improves precision.

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PICAExtraction:
    population: str                    # "adults with initial non-fulminant CDI"
    intervention: str                  # "fidaxomicin"
    comparison: Optional[str]          # "vancomycin"
    outcome: str                       # "recurrence rate, sustained clinical response"
    query_type: str                    # "treatment" | "diagnosis" | "prognosis" | "harm"
    specialty: Optional[str]           # "infectious_disease"
    age_group: Optional[str]           # None | "pediatric" | "adult" | "geriatric"
    sex: Optional[str]                 # None | "male" | "female"
    guideline_bodies: list[str] = field(default_factory=list)  # ["IDSA", "SHEA"]
    drug_names_detected: list[str] = field(default_factory=list)  # ["fidaxomicin", "vancomycin"]

PICO_EXTRACTION_PROMPT = """
Extract the clinical query components. Return valid JSON only.

Query: {query}

{
    "population": "who are the patients? (condition, severity, age if specified)",
    "intervention": "what is being evaluated? (drug, procedure, test)",
    "comparison": "what is being compared to? (null if no comparison)",
    "outcome": "what outcome is being asked about?",
    "query_type": "treatment|diagnosis|prognosis|harm|epidemiology",
    "specialty": "the medical specialty (cardiology|oncology|nephrology|...)",
    "age_group": "null|newborn|infant|child|adolescent|adult|geriatric",
    "sex": "null|male|female",
    "guideline_bodies": ["list of named guideline organisations mentioned"],
    "drug_names_detected": ["all drugs or interventions mentioned by name"]
}
"""
```

---

## Source Priority Routing

```python
from enum import Enum

class SourceTier(int, Enum):
    ICMR = 1                    # Indian Council of Medical Research — highest for India
    INDIAN_SPECIALTY = 2        # CSI, RSSDI, ISN India, IAP, ISG, FOGSI
    INTERNATIONAL_GUIDELINE = 3 # ACC/AHA, ESC, IDSA, ADA, KDIGO, NCCN, ASCO
    FLAGSHIP_GENERAL = 4        # NEJM, Lancet, JAMA, BMJ
    SPECIALTY_PARENT = 5        # Circulation, JACC, JCO, Gastroenterology
    SPECIALTY_CHILD = 6         # JACC:HF, Lancet Oncol, Gut, Hepatology
    SYSTEMATIC_REVIEW = 7       # Cochrane, meta-analyses
    INDIVIDUAL_RCT = 8          # Single RCTs
    COHORT_REVIEW = 9           # Observational, expert review

# Journal ISSN → Source Tier mapping (priority sort key)
JOURNAL_TIER = {
    # ICMR (always Tier 1 for Indian clinical practice)
    "icmr.gov.in": SourceTier.ICMR,
    # International guidelines
    "10.1016/j.jacc": SourceTier.INTERNATIONAL_GUIDELINE,  # JACC guidelines
    "10.1161/CIR": SourceTier.INTERNATIONAL_GUIDELINE,     # Circulation guidelines
    "10.1093/cid": SourceTier.INTERNATIONAL_GUIDELINE,     # Clin Infect Dis (IDSA)
    "10.2337/dc": SourceTier.INTERNATIONAL_GUIDELINE,      # Diabetes Care (ADA SoC)
    # Flagship general
    "10.1056/NEJM": SourceTier.FLAGSHIP_GENERAL,
    "10.1016/S0140-6736": SourceTier.FLAGSHIP_GENERAL,    # Lancet
    "10.1001/jama": SourceTier.FLAGSHIP_GENERAL,
    "10.1136/bmj": SourceTier.FLAGSHIP_GENERAL,
}

def assign_source_tier(doi: str, journal: str, source: str) -> SourceTier:
    """Assign evidence tier for sorting and filtering."""
    source_lower = source.lower()
    doi_prefix = doi[:15] if doi else ""
    
    # ICMR is always highest priority
    if "icmr" in source_lower or "indian council of medical research" in source_lower:
        return SourceTier.ICMR
    
    # Check DOI prefix map
    for prefix, tier in JOURNAL_TIER.items():
        if doi_prefix.startswith(prefix):
            return tier
    
    # Default to systematic review tier for meta-analyses
    pub_types_indicating_sr = ["systematic review", "meta-analysis"]
    if any(t in source_lower for t in pub_types_indicating_sr):
        return SourceTier.SYSTEMATIC_REVIEW
    
    return SourceTier.INDIVIDUAL_RCT  # Conservative default
```

---

## Indian Drug Brand Resolution

Before any PubMed search, resolve Indian brand names to International Nonproprietary Names (INN):

```python
# Core brand→generic map (extend from Indian Medicine Dataset: 253,973 medicines)
BRAND_TO_GENERIC: dict[str, str] = {
    # Analgesics/Antipyretics
    "dolo": "Paracetamol (Acetaminophen)",
    "dolo 650": "Paracetamol 650mg",
    "crocin": "Paracetamol (Acetaminophen)",
    "combiflam": "Ibuprofen + Paracetamol",
    "brufen": "Ibuprofen",
    "voveran": "Diclofenac",
    
    # Antibiotics
    "augmentin": "Amoxicillin + Clavulanic Acid (Co-amoxiclav)",
    "amoxyclav": "Amoxicillin + Clavulanic Acid",
    "zifi": "Cefixime",
    "monocef": "Ceftriaxone",
    "taxim": "Cefotaxime",
    "cifran": "Ciprofloxacin",
    "ciplox": "Ciprofloxacin",
    "azee": "Azithromycin",
    "zithromax": "Azithromycin",
    "o2": "Ofloxacin",
    
    # Cardiovascular
    "ecosprin": "Aspirin (Acetylsalicylic Acid)",
    "loprin": "Aspirin",
    "deplatt": "Clopidogrel",
    "plavix": "Clopidogrel",
    "roseday": "Rosuvastatin",
    "storvas": "Atorvastatin",
    "telma": "Telmisartan",
    "olsar": "Olmesartan",
    "repace": "Losartan",
    "amlong": "Amlodipine",
    
    # Diabetes
    "glycomet": "Metformin",
    "glucophage": "Metformin",
    "januvia": "Sitagliptin",
    "galvus": "Vildagliptin",
    "jardiance": "Empagliflozin",
    "farxiga": "Dapagliflozin",
    "ozempic": "Semaglutide",
    "victoza": "Liraglutide",
    "lantus": "Insulin Glargine",
    "tresiba": "Insulin Degludec",
    
    # Gastrointestinal
    "pan": "Pantoprazole",
    "pantop": "Pantoprazole",
    "omez": "Omeprazole",
    "razo": "Rabeprazole",
    "nexpro": "Esomeprazole",
    "rantac": "Ranitidine",
    "udiliv": "Ursodeoxycholic Acid",
    
    # Respiratory
    "asthalin": "Salbutamol (Albuterol)",
    "seroflo": "Salmeterol + Fluticasone",
    "foracort": "Formoterol + Budesonide",
    "montek": "Montelukast",
    "montair": "Montelukast",
    
    # Psychiatric
    "rexipra": "Escitalopram",
    "nexito": "Escitalopram",
    "restyl": "Alprazolam",
    "lonazep": "Clonazepam",
    "oleanz": "Olanzapine",
    "qutan": "Quetiapine",
    
    # Thyroid
    "eltroxin": "Levothyroxine",
    "thyronorm": "Levothyroxine",
}

def resolve_brand_to_generic(query: str) -> tuple[str, str | None]:
    """
    Find Indian brand names in query and resolve to generic.
    Returns: (resolved_query, brand_detected)
    """
    query_lower = query.lower().strip()
    
    for brand, generic in sorted(BRAND_TO_GENERIC.items(), key=lambda x: -len(x[0])):
        if brand.lower() in query_lower:
            resolved = query_lower.replace(brand.lower(), generic)
            return resolved, brand
    
    return query, None
```

---

## Specialty → Journal Routing

Map detected specialty to priority journal ISSNs and MeSH terms for targeted PubMed searches:

```python
SPECIALTY_CONFIG = {
    "cardiology": {
        "mesh": '"Cardiovascular Diseases"[MeSH]',
        "priority_journals": ["Circulation", "Journal of the American College of Cardiology", "European Heart Journal"],
        "guideline_bodies": ["ACC", "AHA", "ESC", "CSI"],
        "journal_issns": ["0009-7322", "0735-1097", "0195-668X"],
    },
    "oncology": {
        "mesh": '"Neoplasms"[MeSH]',
        "priority_journals": ["Journal of Clinical Oncology", "Lancet Oncology", "Annals of Oncology"],
        "guideline_bodies": ["ASCO", "NCCN", "ESMO"],
        "journal_issns": ["0732-183X", "1470-2045", "0923-7534"],
    },
    "nephrology": {
        "mesh": '"Kidney Diseases"[MeSH] OR "Renal Insufficiency, Chronic"[MeSH]',
        "priority_journals": ["Journal of the American Society of Nephrology", "Kidney International"],
        "guideline_bodies": ["KDIGO", "ASN", "ISN"],
        "journal_issns": ["1046-6673", "0085-2538"],
    },
    "infectious_disease": {
        "mesh": '"Communicable Diseases"[MeSH] OR "Infection"[MeSH]',
        "priority_journals": ["Clinical Infectious Diseases", "Lancet Infectious Diseases"],
        "guideline_bodies": ["IDSA", "ESCMID", "WHO"],
        "journal_issns": ["1058-4838", "1473-3099"],
    },
    "gastroenterology": {
        "mesh": '"Digestive System Diseases"[MeSH]',
        "priority_journals": ["Gastroenterology", "Gut", "Hepatology", "American Journal of Gastroenterology"],
        "guideline_bodies": ["AGA", "ACG", "EASL", "AASLD", "ISG"],
        "journal_issns": ["0016-5085", "0017-5749", "0270-9139"],
    },
    "endocrinology": {
        "mesh": '"Diabetes Mellitus"[MeSH] OR "Endocrine System Diseases"[MeSH]',
        "priority_journals": ["Diabetes Care", "Lancet Diabetes & Endocrinology"],
        "guideline_bodies": ["ADA", "EASD", "Endocrine Society", "RSSDI"],
        "journal_issns": ["0149-5992"],
    },
    "pulmonology": {
        "mesh": '"Lung Diseases"[MeSH] OR "Respiratory Tract Diseases"[MeSH]',
        "priority_journals": ["American Journal of Respiratory and Critical Care Medicine", "European Respiratory Journal"],
        "guideline_bodies": ["ATS", "ERS", "GINA", "GOLD"],
        "journal_issns": ["1073-449X", "0903-1936"],
    },
    "neurology": {
        "mesh": '"Nervous System Diseases"[MeSH]',
        "priority_journals": ["Lancet Neurology", "JAMA Neurology", "Neurology", "Stroke"],
        "guideline_bodies": ["AAN", "EAN", "ASA", "NSI"],
        "journal_issns": ["1474-4422", "2168-6149", "0028-3878"],
    },
    "rheumatology": {
        "mesh": '"Rheumatic Diseases"[MeSH]',
        "priority_journals": ["Annals of the Rheumatic Diseases", "Arthritis & Rheumatology"],
        "guideline_bodies": ["ACR", "EULAR", "IRA"],
        "journal_issns": ["0003-4967", "2326-5191"],
    },
    "pediatrics": {
        "mesh": '"Child"[MeSH] OR "Infant"[MeSH] OR "Adolescent"[MeSH]',
        "priority_journals": ["Pediatrics", "JAMA Pediatrics", "Indian Pediatrics"],
        "guideline_bodies": ["AAP", "IAP"],
        "journal_issns": ["0031-4005", "2168-6211"],
    },
}

def build_specialty_pubmed_query(
    base_query: str,
    specialty: str,
    years: tuple[int, int] = (2020, 2026),
    article_types: list[str] = None,
) -> str:
    """
    Build a PubMed query enriched with specialty-specific MeSH terms.
    """
    config = SPECIALTY_CONFIG.get(specialty, {})
    mesh = config.get("mesh", "")
    
    # Core query with human filter
    human_filter = "NOT (animals[MeSH] NOT humans[MeSH])"
    date_filter = f'("{years[0]}"[PDAT]:"{years[1]}"[PDAT])'
    
    parts = [f"({base_query})"]
    if mesh:
        parts.append(mesh)
    parts.append(human_filter)
    parts.append(date_filter)
    
    if article_types:
        type_filter = " OR ".join(f'"{t}"[pt]' for t in article_types)
        parts.append(f"({type_filter})")
    
    return " AND ".join(parts)
```

---

## Evidence Level Classification

After retrieval, classify each chunk's evidence level for re-ranking weight adjustment:

```python
EVIDENCE_LEVEL_KEYWORDS = {
    "systematic_review": ["systematic review", "meta-analysis", "cochrane", "pooled analysis"],
    "rct": ["randomized controlled trial", "randomised controlled trial", "rct", "placebo-controlled", "double-blind"],
    "guideline": ["clinical practice guideline", "practice guideline", "recommendation", "GRADE", "IDSA", "ACC/AHA", "ICMR"],
    "cohort": ["cohort study", "prospective study", "retrospective study", "observational"],
    "case_report": ["case report", "case series", "n=1", "we report a case"],
}

def classify_evidence_level(text: str, pub_types: list[str]) -> str:
    """Return evidence level string for display and weighting."""
    text_lower = text.lower()
    
    for level, keywords in EVIDENCE_LEVEL_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return level
    
    # Fallback to publication type tags
    pub_lower = " ".join(p.lower() for p in pub_types)
    if "practice guideline" in pub_lower:
        return "guideline"
    if "randomized controlled trial" in pub_lower:
        return "rct"
    if "meta-analysis" in pub_lower or "systematic review" in pub_lower:
        return "systematic_review"
    
    return "review"  # Conservative default
```

---

## Temporal Weighting

Recent evidence should rank higher, but foundational guidelines (even from 2015) must not be buried:

```python
import math
from datetime import datetime

def temporal_weight(pub_year: int | None, base_score: float) -> float:
    """
    Apply temporal decay to retrieval scores.
    
    Recent papers get a boost; very old papers get slight penalty.
    BUT: guidelines from guideline bodies never get penalised — they're authoritative.
    """
    if pub_year is None:
        return base_score
    
    current_year = datetime.now().year
    age = current_year - pub_year
    
    if age <= 2:
        return base_score * 1.15   # Recent boost
    elif age <= 5:
        return base_score * 1.05   # Slight boost for recent
    elif age <= 10:
        return base_score          # No change for 5-10 year old papers
    else:
        return base_score * 0.90   # Slight penalty for >10 year papers
        # Note: caller should exempt guideline-tier sources from this penalty
```

---

## Sex and Age-Specific Retrieval

When the query contains demographic signals, add MeSH filters:

```python
AGE_SIGNALS = {
    "child|paediatric|pediatric|infant|neonate|newborn|baby": '"Child"[MeSH] OR "Infant"[MeSH]',
    "elderly|geriatric|older adult|aged": '"Aged"[MeSH]',
    "adolescent|teenager|teen": '"Adolescent"[MeSH]',
    "pregnant|pregnancy|maternal|gestational": '"Pregnancy"[MeSH]',
}

SEX_SIGNALS = {
    "female|woman|women|girl|she|her": "Female[MeSH]",
    "male|man|men|boy|he|his": "Male[MeSH]",
}

def extract_demographic_filters(query: str) -> dict[str, str | None]:
    """Extract age and sex MeSH filters from query text."""
    query_lower = query.lower()
    filters = {"age": None, "sex": None}
    
    import re
    for pattern, mesh in AGE_SIGNALS.items():
        if re.search(pattern, query_lower):
            filters["age"] = mesh
            break
    
    for pattern, mesh in SEX_SIGNALS.items():
        if re.search(pattern, query_lower):
            filters["sex"] = mesh
            break
    
    return filters
```

---

## Complete Retrieval Orchestration

```python
async def orchestrate_retrieval(
    query: str,
    pico: PICAExtraction,
    qdrant_client,
    ncbi_client,
    tavily_client,
    settings: Settings,
) -> list[dict]:
    """
    Complete multi-source retrieval with source priority ordering.
    """
    # 1. Resolve Indian brand names
    resolved_query, brand = resolve_brand_to_generic(query)
    
    # 2. Build specialty-aware PubMed query
    pubmed_query = build_specialty_pubmed_query(
        base_query=resolved_query,
        specialty=pico.specialty or "general",
        article_types=["Practice Guideline", "Randomized Controlled Trial", "Meta-Analysis", "Systematic Review"],
    )
    
    # 3. Add demographic filters
    demo_filters = extract_demographic_filters(query)
    if demo_filters["age"]:
        pubmed_query += f" AND {demo_filters['age']}"
    
    # 4. Parallel retrieval — fail individually, never fail all
    qdrant_fut = search_qdrant_hybrid(qdrant_client, resolved_query)
    pubmed_fut = search_pubmed(ncbi_client, pubmed_query, max_results=20)
    
    qdrant_results, pubmed_results = await asyncio.gather(
        qdrant_fut, pubmed_fut, return_exceptions=True
    )
    
    all_chunks = []
    
    if not isinstance(qdrant_results, Exception):
        for r in qdrant_results:
            chunk = {
                "content": r.payload["content"],
                "source": r.payload.get("source", ""),
                "pub_year": r.payload.get("pub_year"),
                "score": r.score,
                "source_tier": r.payload.get("source_tier", SourceTier.INDIVIDUAL_RCT),
                "evidence_level": r.payload.get("evidence_level", "review"),
            }
            chunk["weighted_score"] = temporal_weight(chunk["pub_year"], chunk["score"])
            all_chunks.append(chunk)
    
    if not isinstance(pubmed_results, Exception):
        for r in pubmed_results:
            tier = assign_source_tier(r.get("doi", ""), r.get("journal", ""), r.get("source", ""))
            chunk = {
                "content": f"{r['title']}\n\n{r['abstract']}",
                "source": r.get("journal", "PubMed"),
                "pub_year": r.get("pub_year"),
                "score": 0.75,  # Default score for PubMed results
                "source_tier": tier,
                "evidence_level": classify_evidence_level(r["abstract"], r.get("pub_types", [])),
                "pmid": r["pmid"],
                "doi": r.get("doi", ""),
            }
            chunk["weighted_score"] = temporal_weight(chunk["pub_year"], chunk["score"])
            # Boost guideline-tier sources
            if chunk["source_tier"] <= SourceTier.INTERNATIONAL_GUIDELINE:
                chunk["weighted_score"] *= 1.25
            all_chunks.append(chunk)
    
    # 5. Add Tavily only for very recent queries (< 90 days) or sparse results
    if len(all_chunks) < 5:
        tavily_results = await asyncio.to_thread(
            tavily_client.search,
            query=resolved_query,
            search_depth="advanced",
            max_results=5,
        )
        for r in tavily_results.get("results", []):
            if r.get("score", 0) > 0.5:
                all_chunks.append({
                    "content": r["content"][:1500],
                    "source": r["url"],
                    "pub_year": 2025,
                    "score": r["score"] * 0.85,  # Slight penalty vs indexed content
                    "weighted_score": r["score"] * 0.85,
                    "source_tier": SourceTier.INDIVIDUAL_RCT,
                    "evidence_level": "review",
                })
    
    # 6. Sort by weighted score, ICMR always first
    all_chunks.sort(key=lambda x: (x["source_tier"], -x["weighted_score"]))
    
    return all_chunks[:50]  # Top 50 for reranking
```
