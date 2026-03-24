"""
Query understanding layer.

Pipeline (in order):
  0. Preprocess (whitespace normalization)
  1. Medical query normalization (Gemini-powered: expands shorthand, brand→generic, fixes typos)
  2. Language detection → translation to English (Gemini Flash)
  3. Intent classification (zero-shot Gemini Flash)
  4. PICO extraction (10-shot Gemini Flash)
  5. Query expansion (rule-based deterministic fallback + MeSH)

The Gemini normalizer (step 1) handles the long tail of doctor shorthand that static
dictionaries can't cover (context-dependent abbreviations, misspellings, mixed-language).
The static dictionaries in step 5 serve as a fast, zero-cost deterministic fallback.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from xml.sax.saxutils import escape

from shared.config import get_settings
from shared.models.query import (
    MedicalSpecialty,
    PICOElements,
    QueryDemographics,
    QueryIntent,
    QueryMessage,
)
from shared.utils.gemini_client import get_gemini_model, make_generation_config

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Drug brand → generic lookup (Indian market, seeded from CDSCO) ────────────
# Used as deterministic fast-path in _expand_query(). The Gemini normalizer
# covers brands not listed here via its training data.
BRAND_TO_GENERIC: dict[str, str] = {
    # ── Analgesics / Antipyretics ─────────────────────────────────────────
    "crocin": "paracetamol",
    "dolo": "paracetamol",
    "calpol": "paracetamol",
    "combiflam": "ibuprofen-paracetamol",
    "voveran": "diclofenac",
    "ultracet": "tramadol-paracetamol",
    "flexon": "ibuprofen-paracetamol",
    "zerodol": "aceclofenac",
    "zerodol-sp": "aceclofenac-serratiopeptidase",
    # ── Antibiotics ───────────────────────────────────────────────────────
    "augmentin": "amoxicillin-clavulanate",
    "clavam": "amoxicillin-clavulanate",
    "moxclav": "amoxicillin-clavulanate",
    "zithromax": "azithromycin",
    "azee": "azithromycin",
    "azithral": "azithromycin",
    "ciprobay": "ciprofloxacin",
    "cifran": "ciprofloxacin",
    "ciplox": "ciprofloxacin",
    "levoflox": "levofloxacin",
    "levomac": "levofloxacin",
    "oflox": "ofloxacin",
    "taxim": "cefixime",
    "cefixime": "cefixime",
    "monocef": "ceftriaxone",
    "monotax": "ceftriaxone",
    "meronem": "meropenem",
    "linezolid": "linezolid",
    "doxycap": "doxycycline",
    # ── Antidiabetics ─────────────────────────────────────────────────────
    "metformin sr": "metformin",
    "glycomet": "metformin",
    "glyomet": "metformin",
    "gluconorm": "glimepiride-metformin",
    "amaryl": "glimepiride",
    "volix": "voglibose",
    "januvia": "sitagliptin",
    "janumet": "sitagliptin-metformin",
    "galvus": "vildagliptin",
    "galvus met": "vildagliptin-metformin",
    "trajenta": "linagliptin",
    "jardiance": "empagliflozin",
    "forxiga": "dapagliflozin",
    "ryzodeg": "insulin degludec-aspart",
    "lantus": "insulin glargine",
    "humalog": "insulin lispro",
    # ── Cardiovascular ────────────────────────────────────────────────────
    "amlodac": "amlodipine",
    "amlong": "amlodipine",
    "stamlo": "amlodipine",
    "telma": "telmisartan",
    "telmikind": "telmisartan",
    "cardace": "ramipril",
    "enalapril": "enalapril",
    "concor": "bisoprolol",
    "met xl": "metoprolol succinate",
    "betaloc": "metoprolol",
    "atenolol": "atenolol",
    "atorva": "atorvastatin",
    "lipitor": "atorvastatin",
    "rosuvas": "rosuvastatin",
    "crestor": "rosuvastatin",
    "ecosprin": "aspirin",
    "clopitab": "clopidogrel",
    "plavix": "clopidogrel",
    "xarelto": "rivaroxaban",
    "eliquis": "apixaban",
    "enoxarin": "enoxaparin",
    # ── Gastrointestinal ──────────────────────────────────────────────────
    "pantop": "pantoprazole",
    "pan-d": "pantoprazole-domperidone",
    "rablet": "rabeprazole",
    "nexium": "esomeprazole",
    "rantac": "ranitidine",
    "ganaton": "itopride",
    "mucaine": "aluminium hydroxide-magnesium hydroxide",
    "ondansetron": "ondansetron",
    "emeset": "ondansetron",
    # ── Respiratory ───────────────────────────────────────────────────────
    "asthalin": "salbutamol",
    "budecort": "budesonide",
    "foracort": "formoterol-budesonide",
    "seroflo": "salmeterol-fluticasone",
    "montair": "montelukast",
    "montair-lc": "montelukast-levocetirizine",
    "deriphyllin": "theophylline-etophylline",
    # ── Neuro / Psych ─────────────────────────────────────────────────────
    "lonazep": "clonazepam",
    "calmpose": "diazepam",
    "tryptomer": "amitriptyline",
    "nexito": "escitalopram",
    "librium": "chlordiazepoxide",
    "gabapin": "gabapentin",
    "pregabalin": "pregabalin",
    # ── Antihistamines / Allergy ──────────────────────────────────────────
    "allegra": "fexofenadine",
    "cetrizine": "cetirizine",
    "levocet": "levocetirizine",
    "avil": "pheniramine",
    # ── Steroids / Anti-inflammatory ──────────────────────────────────────
    "wysolone": "prednisolone",
    "omnacortil": "prednisolone",
    "defcort": "deflazacort",
    "medrol": "methylprednisolone",
}

# ── Medical abbreviation expansion (regex patterns) ──────────────────────────
# These run in _expand_query() as a deterministic fallback. The Gemini
# normalizer handles these + many more with contextual understanding.
ABBREV_MAP: dict[str, str] = {
    # ── Slash-based clinical abbreviations (Indian doctor shorthand) ──────
    r"(?i)\bk/c/o\b": "known case of",
    r"(?i)\bc/o\b": "complaining of",
    r"(?i)\bh/o\b": "history of",
    r"(?i)\bs/o\b": "suggestive of",
    r"(?i)\bo/e\b": "on examination",
    r"(?i)\ba/w\b": "associated with",
    r"(?i)\br/o\b": "rule out",
    r"(?i)\bf/u\b": "follow up",
    r"(?i)\bf/b\b": "followed by",
    r"(?i)\bd/c\b": "discontinue",
    r"(?i)\bn/v\b": "nausea and vomiting",
    r"(?i)\bs/p\b": "status post",
    r"(?i)\bw/o\b": "without",
    r"(?i)\by/o\b": "year old",
    # ── Standard clinical abbreviations ───────────────────────────────────
    r"\bRx\b": "treatment",
    r"\bHx\b": "history",
    r"\bDx\b": "diagnosis",
    r"\bIx\b": "investigations",
    r"\bSx\b": "symptoms",
    r"\bCx\b": "complications",
    r"\bPMH\b": "past medical history",
    r"\bFH\b": "family history",
    r"\bSH\b": "social history",
    r"\bNAD\b": "no abnormality detected",
    # ── Disease abbreviations ─────────────────────────────────────────────
    r"\bHTN\b": "hypertension",
    r"\bDM\b": "diabetes mellitus",
    r"\bDM2\b": "type 2 diabetes mellitus",
    r"\bDM1\b": "type 1 diabetes mellitus",
    r"\bIHD\b": "ischemic heart disease",
    r"\bCAD\b": "coronary artery disease",
    r"\bCKD\b": "chronic kidney disease",
    r"\bAKI\b": "acute kidney injury",
    r"\bTB\b": "tuberculosis",
    r"\bMDR-TB\b": "multidrug-resistant tuberculosis",
    r"\bCOPD\b": "chronic obstructive pulmonary disease",
    r"\bUTI\b": "urinary tract infection",
    r"\bURTI\b": "upper respiratory tract infection",
    r"\bLRTI\b": "lower respiratory tract infection",
    r"\bCAP\b": "community-acquired pneumonia",
    r"\bHAP\b": "hospital-acquired pneumonia",
    r"\bRHD\b": "rheumatic heart disease",
    r"\bDVT\b": "deep vein thrombosis",
    r"\bPE\b": "pulmonary embolism",
    r"\bGERD\b": "gastroesophageal reflux disease",
    r"\bIBS\b": "irritable bowel syndrome",
    r"\bSLE\b": "systemic lupus erythematosus",
    r"\bRA\b": "rheumatoid arthritis",
    r"\bOA\b": "osteoarthritis",
    # ── Indian clinical / OB-GYN ──────────────────────────────────────────
    r"\bLSCS\b": "lower segment cesarean section",
    r"\bPCOD\b": "polycystic ovarian disease",
    r"\bPCOS\b": "polycystic ovary syndrome",
    r"\bANC\b": "antenatal care",
    r"\bPNC\b": "postnatal care",
    r"\bGDM\b": "gestational diabetes mellitus",
    r"\bAPH\b": "antepartum hemorrhage",
    r"\bPPH\b": "postpartum hemorrhage",
    r"\bNICU\b": "neonatal intensive care unit",
    r"\bOPD\b": "outpatient department",
    r"\bIPD\b": "inpatient department",
    # ── Dosing shorthand ──────────────────────────────────────────────────
    r"(?i)\bbid\b": "twice daily",
    r"(?i)\btid\b": "three times daily",
    r"(?i)\bqid\b": "four times daily",
    r"(?i)\bprn\b": "as needed",
    r"(?i)\bstat\b": "immediately",
    r"(?i)\bpo\b": "oral",
    r"(?i)\bhs\b": "at bedtime",
    r"(?i)\bac\b": "before meals",
    r"(?i)\bpc\b": "after meals",
    # ── Lab tests / Procedures ────────────────────────────────────────────
    r"\bCBC\b": "complete blood count",
    r"\bLFT\b": "liver function test",
    r"\bKFT\b": "kidney function test",
    r"\bRFT\b": "renal function test",
    r"\bHbA1c\b": "glycated hemoglobin",
    r"\bESR\b": "erythrocyte sedimentation rate",
    r"\bCRP\b": "C-reactive protein",
    r"\bTSH\b": "thyroid stimulating hormone",
    r"\bFBS\b": "fasting blood sugar",
    r"\bPPBS\b": "postprandial blood sugar",
    r"\bECG\b": "electrocardiogram",
    r"\bECHO\b": "echocardiogram",
    r"\bUSG\b": "ultrasonography",
    r"\bPFT\b": "pulmonary function test",
    r"\bABG\b": "arterial blood gas",
    # ── Patient / time descriptors ────────────────────────────────────────
    r"(?i)\bpt\b": "patient",
    r"(?i)\bpts\b": "patients",
}

# ── Numeric time patterns (applied separately due to capture groups) ─────────
_TIME_PATTERNS: list[tuple[str, str]] = [
    (r"(\d+)\s*yr(?:s)?\b", r"\1 year"),
    (r"(\d+)\s*mo(?:s)?\b", r"\1 month"),
    (r"(\d+)\s*wk(?:s)?\b", r"\1 week"),
    (r"(\d+)\s*d\b", r"\1 day"),
]

# ── Synonym map (Indian medical vernacular → standard terms) ─────────────────
SYNONYM_MAP: dict[str, str] = {
    "typhoid": "enteric fever",
    "jaundice": "hepatitis",
    "sugar": "diabetes",
    "bp": "blood pressure",
    "heart attack": "myocardial infarction",
    "brain stroke": "cerebrovascular accident",
    "loose motions": "diarrhea",
    "loose motion": "diarrhea",
    "motions": "bowel movements",
    "fits": "seizures",
    "giddiness": "dizziness",
    "burning micturition": "dysuria",
    "burning urine": "dysuria",
    "acidity": "gastroesophageal reflux",
    "gas": "flatulence",
    "gas trouble": "flatulence",
    "piles": "hemorrhoids",
    "stone": "calculus",
    "kidney stone": "renal calculus",
    "fatty liver": "hepatic steatosis",
    "cold": "upper respiratory infection",
    "swelling": "edema",
    "breathlessness": "dyspnea",
    "chest pain": "angina",
    "head injury": "traumatic brain injury",
    "food poisoning": "acute gastroenteritis",
    "water infection": "urinary tract infection",
}

# ── Specialty → MeSH mapping (from Hunt AI Medical Knowledge Graph Part 1) ────
# Used by retrieval layer to augment PubMed queries with precise MeSH terms.
SPECIALTY_MESH_MAP: dict[str, str] = {
    "cardiology": '"Cardiovascular Diseases"[MeSH] AND Humans[MeSH]',
    "oncology": '"Neoplasms"[MeSH] AND Humans[MeSH]',
    "nephrology": '"Kidney Diseases"[MeSH] AND Humans[MeSH]',
    "neurology": '"Nervous System Diseases"[MeSH] AND Humans[MeSH]',
    "pulmonology": '"Lung Diseases"[MeSH] AND Humans[MeSH]',
    "gastroenterology": '"Digestive System Diseases"[MeSH] AND Humans[MeSH]',
    "endocrinology": '"Endocrine System Diseases"[MeSH] AND Humans[MeSH]',
    "rheumatology": '"Rheumatic Diseases"[MeSH] AND Humans[MeSH]',
    "infectious_disease": '"Communicable Diseases"[MeSH] AND Humans[MeSH]',
    "pediatrics": '"Child"[MeSH] OR "Infant"[MeSH] OR "Adolescent"[MeSH]',
    "geriatrics": '"Aged"[MeSH] OR "Aged, 80 and over"[MeSH]',
    "psychiatry": '"Mental Disorders"[MeSH] AND Humans[MeSH]',
    "dermatology": '"Skin Diseases"[MeSH] AND Humans[MeSH]',
    "ophthalmology": '"Eye Diseases"[MeSH] AND Humans[MeSH]',
    "obstetrics_gynecology": '"Pregnancy Complications"[MeSH] OR "Genital Diseases, Female"[MeSH]',
    "orthopedics": '"Musculoskeletal Diseases"[MeSH] AND Humans[MeSH]',
    "urology": '"Urologic Diseases"[MeSH] AND Humans[MeSH]',
    "hematology": '"Hematologic Diseases"[MeSH] AND Humans[MeSH]',
    "critical_care": '"Critical Care"[MeSH] AND Humans[MeSH]',
    "emergency_medicine": '"Emergency Medicine"[MeSH] AND Humans[MeSH]',
}

# ── Specialty → Priority journal ISSNs (from Knowledge Graph Part 5) ──────────
# Used by retrieval layer to boost documents from specialty-appropriate journals.
SPECIALTY_JOURNAL_PRIORITY: dict[str, list[str]] = {
    "cardiology": ["0009-7322", "0735-1097", "0195-668X"],  # Circulation, JACC, EHJ
    "oncology": ["0732-183X", "1470-2045", "0923-7534"],  # JCO, Lancet Oncol, Ann Oncol
    "nephrology": ["1046-6673", "0085-2538"],  # JASN, Kidney Int
    "gastroenterology": ["0016-5085", "0017-5749", "0270-9139"],  # Gastro, Gut, Hepatology
    "infectious_disease": ["1058-4838", "1473-3099"],  # CID, Lancet ID
    "endocrinology": ["0149-5992", "0021-972X"],  # Diabetes Care, JCEM
    "pulmonology": ["1073-449X", "0903-1936"],  # AJRCCM, ERJ
    "neurology": ["1474-4422", "0028-3878"],  # Lancet Neurol, Neurology
    "rheumatology": ["0003-4967", "2326-5191"],  # Ann Rheum Dis, A&R
    "psychiatry": ["0002-953X", "2215-0366"],  # Am J Psychiatry, Lancet Psychiatry
    "pediatrics": ["0031-4005", "2168-6211"],  # Pediatrics, JAMA Pediatrics
    "obstetrics_gynecology": ["0002-9378", "1470-0328"],  # AJOG, BJOG
    "hematology": ["0006-4971", "0887-6924"],  # Blood, Leukemia
    "dermatology": ["2168-6068", "0007-0963"],  # JAMA Derm, BJD
    "ophthalmology": ["0161-6420", "2168-6173"],  # Ophthalmology, JAMA Ophthalmol
}

# ── Guideline body recognition (from Knowledge Graph Part 6) ──────────────────
# Maps guideline body names/acronyms to canonical forms for routing.
GUIDELINE_BODIES: dict[str, str] = {
    "icmr": "ICMR", "indian council of medical research": "ICMR",
    "who": "WHO", "world health organization": "WHO",
    "acc": "ACC/AHA", "aha": "ACC/AHA", "acc/aha": "ACC/AHA",
    "esc": "ESC", "european society of cardiology": "ESC",
    "nccn": "NCCN", "asco": "ASCO", "esmo": "ESMO",
    "kdigo": "KDIGO", "ada": "ADA", "american diabetes association": "ADA",
    "rssdi": "RSSDI", "idsa": "IDSA", "idsa/shea": "IDSA/SHEA",
    "escmid": "ESCMID", "ats": "ATS/ERS", "ers": "ATS/ERS",
    "gina": "GINA", "gold": "GOLD",
    "acr": "ACR/EULAR", "eular": "ACR/EULAR",
    "aga": "AGA", "acg": "ACG", "aasld": "AASLD", "easl": "EASL",
    "apa": "APA", "aap": "AAP", "iap": "IAP",
    "acog": "ACOG", "cochrane": "Cochrane",
    "csi": "CSI", "cardiological society of india": "CSI",
    "nice": "NICE", "sign": "SIGN",
}

# ── Intent routing table ───────────────────────────────────────────────────────
INTENT_DESCRIPTIONS = {
    "drug_lookup": "Question about a specific drug: dosage, indications, contraindications, brand names",
    "guideline_query": "Question about clinical guidelines, protocols, or standard of care",
    "research_question": "Question about clinical evidence, trial results, or research findings",
    "drug_interaction": "Question about interactions between two or more drugs",
    "epidemiology": "Question about disease prevalence, incidence, or population statistics",
}

# ── PICO few-shot examples (10 examples for diverse Indian clinical queries) ──
PICO_FEW_SHOTS = """
Example 1:
Query: "Is azithromycin better than doxycycline for community-acquired pneumonia in adults?"
PICO: {"population": "adults with community-acquired pneumonia", "intervention": "azithromycin", "comparison": "doxycycline", "outcome": "treatment efficacy"}

Example 2:
Query: "What is the recommended first-line treatment for type 2 diabetes in India?"
PICO: {"population": "patients with type 2 diabetes in India", "intervention": "first-line treatment", "comparison": null, "outcome": "glycemic control"}

Example 3:
Query: "Does aspirin reduce cardiovascular events in primary prevention?"
PICO: {"population": "patients without established cardiovascular disease", "intervention": "aspirin", "comparison": "placebo or no treatment", "outcome": "cardiovascular events including MI and stroke"}

Example 4:
Query: "ICMR guidelines for MDR-TB treatment duration"
PICO: {"population": "patients with multidrug-resistant tuberculosis", "intervention": "MDR-TB treatment regimen", "comparison": null, "outcome": "treatment duration and cure rate"}

Example 5:
Query: "Metformin versus insulin in gestational diabetes management"
PICO: {"population": "pregnant women with gestational diabetes", "intervention": "metformin", "comparison": "insulin", "outcome": "maternal and neonatal outcomes"}

Example 6:
Query: "Can I give ciprofloxacin with theophylline in a COPD patient?"
PICO: {"population": "patients with chronic obstructive pulmonary disease on theophylline", "intervention": "ciprofloxacin co-administration", "comparison": null, "outcome": "drug interaction risk and theophylline toxicity"}

Example 7:
Query: "Amoxicillin dose for 5 year old child with acute otitis media"
PICO: {"population": "5 year old child with acute otitis media", "intervention": "amoxicillin", "comparison": null, "outcome": "appropriate pediatric dosage and resolution"}

Example 8:
Query: "Dengue fever management guidelines India — when to transfuse platelets?"
PICO: {"population": "patients with dengue fever in India", "intervention": "platelet transfusion", "comparison": "conservative management without transfusion", "outcome": "platelet transfusion threshold and clinical outcomes"}

Example 9:
Query: "Preeclampsia prevention — low dose aspirin vs calcium supplementation in high risk ANC"
PICO: {"population": "high-risk antenatal women", "intervention": "low-dose aspirin", "comparison": "calcium supplementation", "outcome": "preeclampsia prevention"}

Example 10:
Query: "Medical vs surgical management of ectopic pregnancy — when to operate?"
PICO: {"population": "women with ectopic pregnancy", "intervention": "surgical management (laparoscopy/laparotomy)", "comparison": "medical management (methotrexate)", "outcome": "treatment success rate and indications for surgery"}
"""

# ── Gemini-powered medical query normalizer prompt ────────────────────────────
# Agent: Query Understanding (Stage 0 — medical language normalization)
# Model: Gemini Flash
# Purpose: Expand doctor shorthand, brand→generic, fix misspellings, normalize
#          time/patient descriptors. Runs BEFORE translation because Indian doctors
#          mix Hindi/regional language with English medical abbreviations.
_NORMALIZER_PROMPT = """\
<system_instruction>
  <identity>
    <role>Indian clinical language normalizer</role>
    <mission>Expand a doctor's shorthand WhatsApp query into a clear, fully-expanded
    English medical query. Preserve clinical meaning exactly.</mission>
  </identity>

  <rules>
    <rule>Expand ALL medical abbreviations: c/o → complaining of, h/o → history of,
    k/c/o → known case of, s/o → suggestive of, o/e → on examination, Rx → treatment,
    Dx → diagnosis, Hx → history, Ix → investigations, bid → twice daily, tid → three
    times daily, qid → four times daily, OD → once daily, prn → as needed, stat → immediately,
    po → oral, iv → intravenous, im → intramuscular, sc → subcutaneous.</rule>
    <rule>Convert Indian brand names to generic names, keeping brand in parentheses.
    Example: glycomet → metformin (Glycomet), dolo → paracetamol (Dolo).</rule>
    <rule>Expand patient descriptors: "45M" → "45 year old male", "3d" → "3 days",
    "2wk" → "2 weeks", "6mo" → "6 months".</rule>
    <rule>Expand lab/test abbreviations: CBC, LFT, KFT, HbA1c, ESR, CRP, TSH, ECG, USG, etc.</rule>
    <rule>Expand disease abbreviations: DM2 → type 2 diabetes mellitus, HTN → hypertension,
    COPD → chronic obstructive pulmonary disease, LSCS → cesarean section, PCOD/PCOS, UTI, etc.</rule>
    <rule>Fix obvious medical misspellings (diabets → diabetes, hypertention → hypertension).</rule>
    <rule>Do NOT add clinical information not present in the original query.</rule>
    <rule>Do NOT change the medical question being asked — only expand and clarify.</rule>
    <rule>If the input is already clear English with no abbreviations, return it unchanged.</rule>
  </rules>

  <examples>
    <example>
      <input>45M k/c/o DM2 on glycomet 500 bid c/o giddiness x 3d</input>
      <output>45 year old male, known case of type 2 diabetes mellitus on metformin (Glycomet) 500mg twice daily, complaining of dizziness for 3 days</output>
    </example>
    <example>
      <input>pt h/o LSCS 2yr back now ANC 12wk, HbA1c 6.8, Rx?</input>
      <output>patient with history of lower segment cesarean section 2 years back, now antenatal care at 12 weeks, glycated hemoglobin 6.8, what is the treatment?</output>
    </example>
    <example>
      <input>URTI in 5yr child, rx augmentin or azee?</input>
      <output>upper respiratory tract infection in 5 year old child, treatment with amoxicillin-clavulanate (Augmentin) or azithromycin (Azee)?</output>
    </example>
    <example>
      <input>60F k/c/o HTN CKD stage 3 on telma 40 + ecosprin, now KFT deranged creatinine 3.2, Rx adjustment?</input>
      <output>60 year old female, known case of hypertension and chronic kidney disease stage 3 on telmisartan (Telma) 40mg and aspirin (Ecosprin), now kidney function test deranged with creatinine 3.2, treatment adjustment?</output>
    </example>
    <example>
      <input>neonate 28wk preterm in NICU, RDS on CPAP, surfactant dose?</input>
      <output>neonate born at 28 weeks preterm in neonatal intensive care unit, respiratory distress syndrome on continuous positive airway pressure, surfactant dose?</output>
    </example>
    <example>
      <input>What is the first-line treatment for MDR-TB in India?</input>
      <output>What is the first-line treatment for multidrug-resistant tuberculosis in India?</output>
    </example>
  </examples>

  <output_format>
    Return JSON only: {"normalized": "<expanded query>", "abbreviations_found": ["abbr1", "abbr2"]}
  </output_format>

  <input>
    <query>{query}</query>
  </input>
</system_instruction>
"""


class QueryUnderstanding:
    def __init__(self) -> None:
        self._flash = get_gemini_model(settings.gemini_model_primary)
        self._flash_config = make_generation_config(
            temperature=0.0, top_p=1.0, max_output_tokens=1024, json_mode=True
        )
        self._normalizer_config = make_generation_config(
            temperature=0.0, top_p=1.0, max_output_tokens=512, json_mode=True
        )

    async def process(self, msg: QueryMessage) -> QueryMessage:
        """Run the full query understanding pipeline on a QueryMessage."""
        # Step 0: Preprocess (whitespace normalization)
        msg.raw_text = _preprocess(msg.raw_text)

        # Step 1: Gemini-powered medical query normalization
        msg.normalized_text = await self._normalize_medical_query(msg.raw_text)

        # Use normalized text for all downstream steps
        working_text = msg.normalized_text or msg.raw_text

        # Step 1b: Detect guideline body from raw text (fast regex, no API cost)
        msg.guideline_body = _detect_guideline_body(working_text)

        # Step 2: Detect language and translate to English
        msg = await self._translate(msg)

        # Step 3: Classify intent (use translated or normalized text)
        query_for_analysis = msg.translated_text or working_text
        msg.intent = await self._classify_intent(query_for_analysis)

        # Step 4: Extract PICO + specialty + demographics (combined Gemini call)
        pico, specialty, demographics = await self._extract_pico_specialty(query_for_analysis)
        msg.pico = pico
        msg.specialty = specialty
        msg.demographics = demographics

        # Step 5: Rule-based query expansion (deterministic fallback)
        msg.expanded_queries = _expand_query(query_for_analysis)

        return msg

    async def _normalize_medical_query(self, raw_text: str) -> str:
        """
        Gemini-powered medical query normalizer.

        Expands doctor shorthand (c/o, h/o, k/c/o, bid, etc.), converts brand
        names to generics, fixes misspellings, and normalizes time/patient
        descriptors. Runs BEFORE translation because Indian doctors mix
        Hindi/regional language with English-based medical abbreviations.

        Falls back to raw_text if the Gemini call fails.
        """
        prompt = _NORMALIZER_PROMPT.format(query=escape(raw_text))
        try:
            response = await self._flash.generate_content_async(
                prompt, generation_config=self._normalizer_config
            )
            data = json.loads(response.text)
            normalized = data.get("normalized", raw_text)
            abbrevs = data.get("abbreviations_found", [])
            if abbrevs:
                logger.info(
                    "Normalized query — expanded %d abbreviation(s): %s",
                    len(abbrevs), ", ".join(abbrevs[:10]),
                )
            return normalized
        except Exception as e:
            logger.warning("Medical normalizer failed, using raw text: %s", e)
            return raw_text

    async def _translate(self, msg: QueryMessage) -> QueryMessage:
        """Detect language and translate to English if needed."""
        text = msg.normalized_text or msg.raw_text

        # Fast path: already detected as English
        if msg.language_code == "en":
            msg.translated_text = text
            return msg

        # ── Translation prompt (XML-structured) ───────────────────────────
        # Agent: Query Understanding (Stage 2 — translation)
        # Model: Gemini Flash
        prompt = (
            "<system_instruction>\n"
            "  <identity>\n"
            "    <role>Medical query translator</role>\n"
            "    <mission>Translate a medical query to English with clinical precision.</mission>\n"
            "  </identity>\n"
            "\n"
            "  <rules>\n"
            "    <rule>Preserve ALL drug names exactly as written (brand or generic).</rule>\n"
            "    <rule>Preserve gene mutations, anatomical terms, and medical abbreviations.</rule>\n"
            "    <rule>Do not add, remove, or rephrase clinical intent.</rule>\n"
            "  </rules>\n"
            "\n"
            "  <output_format>\n"
            '    Return JSON only: {"translated": "<English translation>"}\n'
            "  </output_format>\n"
            "\n"
            "  <input>\n"
            f"    <query>{escape(text)}</query>\n"
            "  </input>\n"
            "</system_instruction>"
        )
        response = await self._flash.generate_content_async(
            prompt, generation_config=self._flash_config
        )
        try:
            data = json.loads(response.text)
            msg.translated_text = data.get("translated", text)
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Translation failed; using normalized text")
            msg.translated_text = text

        return msg

    async def _classify_intent(self, query: str) -> QueryIntent:
        intent_list = "\n".join(
            f'- "{k}": {v}' for k, v in INTENT_DESCRIPTIONS.items()
        )
        # ── Intent classification prompt (XML-structured) ──────────────────
        # Agent: Query Understanding (Stage 3 — intent routing)
        # Model: Gemini Flash
        prompt = (
            "<system_instruction>\n"
            "  <identity>\n"
            "    <role>Medical query intent classifier</role>\n"
            "    <mission>Classify a clinical query into exactly one intent category.</mission>\n"
            "  </identity>\n"
            "\n"
            "  <intent_definitions>\n"
            f"    {intent_list}\n"
            "  </intent_definitions>\n"
            "\n"
            "  <rules>\n"
            "    <rule>Select exactly ONE intent — the most specific match.</rule>\n"
            "    <rule>When ambiguous, prefer 'research_question' as the default.</rule>\n"
            "  </rules>\n"
            "\n"
            "  <output_format>\n"
            '    Return JSON only: {"intent": "<intent_name>"}\n'
            "  </output_format>\n"
            "\n"
            "  <input>\n"
            f"    <query>{escape(query)}</query>\n"
            "  </input>\n"
            "</system_instruction>"
        )
        response = await self._flash.generate_content_async(
            prompt, generation_config=self._flash_config
        )
        try:
            data = json.loads(response.text)
            intent = data.get("intent", "research_question")
            if intent not in INTENT_DESCRIPTIONS:
                intent = "research_question"
            return intent  # type: ignore[return-value]
        except (json.JSONDecodeError, AttributeError):
            return "research_question"

    async def _extract_pico_specialty(
        self, query: str
    ) -> tuple[PICOElements, MedicalSpecialty | None, QueryDemographics | None]:
        """
        Combined PICO + specialty + demographics extraction in a single Gemini call.

        Merging these avoids 3 separate API calls. The model extracts:
        - PICO elements (population, intervention, comparison, outcome)
        - Medical specialty for journal/MeSH routing
        - Patient demographics (age_group, sex) for PubMed filtering
        """
        specialty_list = ", ".join([
            "cardiology", "oncology", "nephrology", "neurology", "pulmonology",
            "gastroenterology", "endocrinology", "rheumatology", "infectious_disease",
            "pediatrics", "geriatrics", "psychiatry", "dermatology", "ophthalmology",
            "obstetrics_gynecology", "orthopedics", "urology", "hematology",
            "critical_care", "emergency_medicine", "general_medicine",
        ])
        # ── Combined PICO + specialty + demographics prompt ──────────────────
        # Agent: Query Understanding (Stage 4 — structured extraction)
        # Model: Gemini Flash
        prompt = (
            "<system_instruction>\n"
            "  <identity>\n"
            "    <role>Medical query analyzer</role>\n"
            "    <mission>Extract PICO elements, medical specialty, and patient demographics\n"
            "    from a clinical query. This drives evidence retrieval routing.</mission>\n"
            "  </identity>\n"
            "\n"
            "  <rules>\n"
            "    <rule>Extract PICO: Population, Intervention, Comparison, Outcome. Use null for absent elements.</rule>\n"
            "    <rule>Be specific in PICO — include disease stage, geography, age group when stated.</rule>\n"
            f"    <rule>Classify specialty from: {specialty_list}. Use general_medicine if unclear.</rule>\n"
            "    <rule>Extract patient demographics when present: age_group (newborn, infant, child,\n"
            "    adolescent, adult, middle_aged, aged, elderly) and sex (male, female). Use null if not stated.</rule>\n"
            "    <rule>For pediatric queries (mentions child, infant, neonate, or age &lt;18), set specialty to pediatrics.</rule>\n"
            "    <rule>For queries mentioning pregnancy, LSCS, ANC, set specialty to obstetrics_gynecology.</rule>\n"
            "  </rules>\n"
            "\n"
            "  <examples>\n"
            f"    {PICO_FEW_SHOTS}\n"
            "  </examples>\n"
            "\n"
            "  <output_format>\n"
            "    Return JSON:\n"
            "    {\n"
            '      "population": "..." or null,\n'
            '      "intervention": "..." or null,\n'
            '      "comparison": "..." or null,\n'
            '      "outcome": "..." or null,\n'
            '      "specialty": "<one of the specialty values>",\n'
            '      "age_group": "<age group>" or null,\n'
            '      "sex": "male" or "female" or null\n'
            "    }\n"
            "  </output_format>\n"
            "\n"
            "  <input>\n"
            f"    <query>{escape(query)}</query>\n"
            "  </input>\n"
            "</system_instruction>"
        )
        response = await self._flash.generate_content_async(
            prompt, generation_config=self._flash_config
        )
        try:
            data = json.loads(response.text)
            pico = PICOElements(
                population=data.get("population"),
                intervention=data.get("intervention"),
                comparison=data.get("comparison"),
                outcome=data.get("outcome"),
            )
            specialty = data.get("specialty")
            if specialty and specialty not in MedicalSpecialty.__args__:
                specialty = "general_medicine"
            demographics = None
            if data.get("age_group") or data.get("sex"):
                demographics = QueryDemographics(
                    age_group=data.get("age_group"),
                    sex=data.get("sex"),
                )
            return pico, specialty, demographics
        except (json.JSONDecodeError, AttributeError, TypeError) as e:
            logger.warning("PICO/specialty extraction failed: %s", e)
            return PICOElements(), None, None


def _detect_guideline_body(text: str) -> str | None:
    """Detect named guideline bodies in the query text (regex, zero API cost)."""
    text_lower = text.lower()
    for pattern, canonical in GUIDELINE_BODIES.items():
        if re.search(r"\b" + re.escape(pattern) + r"\b", text_lower):
            return canonical
    return None


def _preprocess(text: str) -> str:
    """Normalize whitespace and strip leading/trailing space."""
    return re.sub(r"\s+", " ", text).strip()


def _expand_query(query: str) -> list[str]:
    """
    Rule-based query expansion (deterministic, zero API cost):
    1. Expand abbreviations via regex
    2. Expand time patterns (3d → 3 day)
    3. Map synonyms
    4. Map brand names to generics
    Returns list of expanded query variants to use as retrieval sub-queries.
    """
    expanded = query.lower()

    for pattern, replacement in ABBREV_MAP.items():
        expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)

    for pattern, replacement in _TIME_PATTERNS:
        expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)

    for source, target in SYNONYM_MAP.items():
        expanded = expanded.replace(source, target)

    generic_expanded = expanded
    for brand, generic in BRAND_TO_GENERIC.items():
        if brand in expanded:
            generic_expanded = expanded.replace(brand, generic)

    variants = list({query, expanded})
    if generic_expanded != expanded:
        variants.append(generic_expanded)

    return variants
