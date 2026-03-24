"""
OpenEvidence 10-query benchmark set for Hunt AI playground.

Each query includes:
  - The full clinical question
  - Difficulty tier (easy / medium / hard)
  - Key expected topics in a good answer (for manual quality assessment)

Source: OpenEvidence reference answers from /Users/admin/Documents/Open Work/openevidence.md
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BenchmarkQuery:
    id: int
    difficulty: str          # "easy", "medium", "hard"
    query: str
    expected_topics: list[str]  # key concepts a good answer must mention
    reference_summary: str      # 1-2 sentence gold-standard summary


BENCHMARK_QUERIES: list[BenchmarkQuery] = [
    # ── Easy (3) ─────────────────────────────────────────────────────────────
    BenchmarkQuery(
        id=1,
        difficulty="easy",
        query=(
            "According to recent IDSA and SHEA guidelines, what is the preferred "
            "first-line treatment for an initial episode of non-fulminant "
            "Clostridioides difficile infection in adults, and how does it compare "
            "to vancomycin in terms of recurrence?"
        ),
        expected_topics=[
            "fidaxomicin preferred first-line",
            "200 mg twice daily for 10 days",
            "vancomycin acceptable alternative",
            "lower recurrence rates with fidaxomicin",
            "narrower spectrum preserves gut microbiota",
        ],
        reference_summary=(
            "Fidaxomicin is preferred over vancomycin for initial non-fulminant CDI "
            "due to equivalent cure rates but significantly lower recurrence (~16% vs ~25%)."
        ),
    ),
    BenchmarkQuery(
        id=2,
        difficulty="easy",
        query=(
            "What are the key CT findings that differentiate acute ischemic stroke "
            "from intracerebral hemorrhage on non-contrast head CT, including the "
            "hyperdense MCA sign and loss of gray-white differentiation?"
        ),
        expected_topics=[
            "loss of gray-white differentiation",
            "insular ribbon sign",
            "hyperdense MCA sign (thrombus)",
            "sulcal effacement",
            "hyperdense region for hemorrhage",
            "sensitivity ~30-52% for hyperdense MCA",
        ],
        reference_summary=(
            "Ischemic stroke shows loss of gray-white differentiation, sulcal effacement, "
            "and hyperdense MCA sign; hemorrhage shows hyperdense parenchymal blood."
        ),
    ),
    BenchmarkQuery(
        id=3,
        difficulty="easy",
        query=(
            "For a patient with newly diagnosed HFrEF (LVEF ≤40%), what do current "
            "ESC/ACC/AHA guidelines recommend as foundational pharmacologic therapy "
            "(drug classes and sequence)?"
        ),
        expected_topics=[
            "ARNI (sacubitril/valsartan) preferred over ACEi/ARB",
            "beta-blocker (carvedilol, metoprolol succinate, bisoprolol)",
            "MRA (spironolactone or eplerenone)",
            "SGLT2 inhibitor (dapagliflozin or empagliflozin)",
            "all four classes within 3 months",
            "no mandatory sequence",
        ],
        reference_summary=(
            "Four foundational classes: ARNI, beta-blocker, MRA, SGLT2i — initiate all "
            "early and rapidly as tolerated, ideally within 3 months."
        ),
    ),

    # ── Medium (3) ───────────────────────────────────────────────────────────
    BenchmarkQuery(
        id=4,
        difficulty="medium",
        query=(
            "Compare apixaban and rivaroxaban for stroke prevention in non-valvular "
            "atrial fibrillation, focusing on efficacy, major bleeding risk, and key "
            "differences in patients with moderate chronic kidney disease (eGFR 30–50 mL/min)."
        ),
        expected_topics=[
            "similar stroke prevention efficacy",
            "apixaban lower major bleeding risk",
            "apixaban ~25% renal excretion vs rivaroxaban ~36%",
            "apixaban preferred in CKD",
            "dose adjustments for both in CKD",
        ],
        reference_summary=(
            "Apixaban is favored over rivaroxaban in AF with moderate CKD due to lower "
            "major bleeding risk with similar stroke prevention efficacy."
        ),
    ),
    BenchmarkQuery(
        id=5,
        difficulty="medium",
        query=(
            "In adults with moderate-to-severe ulcerative colitis who have failed "
            "anti-TNF therapy, what do recent ACG/ECCO guidelines recommend regarding "
            "the choice between vedolizumab and ustekinumab, and what are the main "
            "differences in efficacy and safety?"
        ),
        expected_topics=[
            "switch to different mechanism of action",
            "ustekinumab likely more effective than vedolizumab",
            "ustekinumab higher induction remission rates",
            "vedolizumab gut-selective",
            "both safe, low serious adverse events",
        ],
        reference_summary=(
            "Ustekinumab is likely more effective than vedolizumab for anti-TNF-experienced "
            "moderate-severe UC, but both are safe and reasonable choices per ACG/ECCO."
        ),
    ),
    BenchmarkQuery(
        id=6,
        difficulty="medium",
        query=(
            "For post-menopausal women with early-stage, hormone receptor-positive, "
            "HER2-negative breast cancer, how do current ASCO/ESMO guidelines recommend "
            "using genomic assays (e.g., Oncotype DX, MammaPrint) to guide decisions "
            "about adjuvant chemotherapy?"
        ),
        expected_topics=[
            "Oncotype DX for node-negative and 1-3 node-positive",
            "RS 0-25 no chemo benefit (RxPONDER)",
            "MammaPrint for high clinical risk",
            "MINDACT trial",
            "shared decision-making",
            "not for HER2+ or triple-negative",
        ],
        reference_summary=(
            "Oncotype DX and MammaPrint guide adjuvant chemo decisions in HR+/HER2- breast "
            "cancer; chemo generally omitted for low genomic risk in node-negative or 1-3 node+ disease."
        ),
    ),

    # ── Hard (4) ─────────────────────────────────────────────────────────────
    BenchmarkQuery(
        id=7,
        difficulty="hard",
        query=(
            "In patients with metastatic non-small cell lung cancer, EGFR exon 20 "
            "insertion mutations, and no prior targeted therapy, how do current "
            "guidelines and key trials position amivantamab versus mobocertinib, "
            "including efficacy, toxicity, and sequencing with platinum-based "
            "chemotherapy and immunotherapy?"
        ),
        expected_topics=[
            "amivantamab + platinum-pemetrexed first-line (PAPILLON)",
            "PFS 11.4 vs 6.7 months",
            "mobocertinib failed first-line (EXCLAIM-2)",
            "mobocertinib reserved for post-platinum",
            "immunotherapy not effective in EGFR-mutant",
            "amivantamab: infusion reactions, rash, paronychia",
            "mobocertinib: diarrhea, QTc prolongation",
        ],
        reference_summary=(
            "Amivantamab + platinum-pemetrexed is preferred first-line for EGFR exon 20 "
            "insertion NSCLC (PAPILLON trial); mobocertinib is not recommended first-line."
        ),
    ),
    BenchmarkQuery(
        id=8,
        difficulty="hard",
        query=(
            "For type 2 diabetes with established ASCVD and CKD (eGFR 25–45 mL/min), "
            "what is the recommended combination and sequencing of SGLT2 inhibitors "
            "and GLP-1 receptor agonists according to ADA and KDIGO guidance, and how "
            "should therapy be adjusted as eGFR declines below 30?"
        ),
        expected_topics=[
            "SGLT2i first for cardiorenal protection",
            "initiate if eGFR ≥20",
            "continue as eGFR declines",
            "GLP-1 RA add-on for ASCVD benefit",
            "GLP-1 RA effective at all CKD stages",
            "don't newly initiate SGLT2i below eGFR 20",
        ],
        reference_summary=(
            "Initiate SGLT2i first (if eGFR ≥20), add GLP-1 RA for further ASCVD benefit; "
            "continue SGLT2i as eGFR declines, prioritize GLP-1 RA below eGFR 30."
        ),
    ),
    BenchmarkQuery(
        id=9,
        difficulty="hard",
        query=(
            "How do recent AHA/ASA guidelines compare tenecteplase versus alteplase "
            "for acute ischemic stroke thrombolysis, including dose, indications, "
            "non-inferiority/superiority data, and specific scenarios where tenecteplase "
            "is preferred or not recommended?"
        ),
        expected_topics=[
            "tenecteplase 0.25 mg/kg IV bolus non-inferior",
            "alteplase 0.9 mg/kg over 1 hour",
            "similar efficacy and safety",
            "tenecteplase preferred for prehospital/transfer",
            "preferred when EVT planned",
            "do NOT use 0.4 mg/kg dose",
        ],
        reference_summary=(
            "Tenecteplase 0.25 mg/kg is non-inferior to alteplase for acute ischemic stroke; "
            "preferred for rapid administration scenarios (prehospital, EVT-planned)."
        ),
    ),
    BenchmarkQuery(
        id=10,
        difficulty="hard",
        query=(
            "In severe asthma with eosinophilic phenotype and frequent exacerbations "
            "despite high-dose ICS/LABA, how should clinicians choose between "
            "mepolizumab, benralizumab, dupilumab, and tezepelumab based on biomarker "
            "profiles (eosinophils, FeNO, IgE), comorbidities, and head-to-head or "
            "indirect comparative evidence?"
        ),
        expected_topics=[
            "mepolizumab/benralizumab for high BEC ≥300-500",
            "dupilumab/tezepelumab for broader BEC range",
            "elevated FeNO favors dupilumab/tezepelumab",
            "dupilumab preferred with atopic comorbidities",
            "tezepelumab effective in non-eosinophilic asthma",
            "no head-to-head RCTs",
            "steroid-sparing: mepolizumab, benralizumab",
        ],
        reference_summary=(
            "Mepolizumab/benralizumab for high eosinophils + OCS dependence; dupilumab for "
            "allergic comorbidities; tezepelumab for broadest biomarker coverage including non-eosinophilic."
        ),
    ),
]


def get_queries_by_difficulty(difficulty: str | None = None) -> list[BenchmarkQuery]:
    """Filter benchmark queries by difficulty level."""
    if difficulty is None:
        return BENCHMARK_QUERIES
    return [q for q in BENCHMARK_QUERIES if q.difficulty == difficulty]
