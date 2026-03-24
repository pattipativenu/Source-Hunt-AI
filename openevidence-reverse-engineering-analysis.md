# Reverse-Engineering OpenEvidence: Forensic Analysis of Query Processing

## How OpenEvidence Thinks, Retrieves, and Constructs Answers

This document forensically deconstructs three OpenEvidence responses (one easy, one medium, one hard) from the 10-query benchmark set. For each query, we trace: how the system likely decomposed the question, what search queries it executed, why it selected each specific reference, which claims map to which sources, and what retrieval strategy produced this particular answer structure.

---

## Analysis 1: EASY — C. difficile First-Line Treatment (Question 1)

### The Query
> "According to recent IDSA and SHEA guidelines, what is the preferred first-line treatment for an initial episode of non-fulminant Clostridioides difficile infection in adults, and how does it compare to vancomycin in terms of recurrence?"

### Step 1: How OpenEvidence Likely Decomposed This Query

The query contains explicit signal words that a query understanding agent would parse:

**Extracted entities:**
- **Guideline body:** "IDSA and SHEA" — this is a named guideline, not a general question
- **Condition:** "Clostridioides difficile infection" (CDI)
- **Qualifier:** "initial episode," "non-fulminant," "adults"
- **Drug comparison:** fidaxomicin vs vancomycin (implied by "preferred first-line" and "compare to vancomycin")
- **Outcome of interest:** "recurrence"

**PICO extraction:**
- P: Adults with initial, non-fulminant CDI
- I: Preferred first-line treatment (fidaxomicin)
- C: Vancomycin
- O: Recurrence rates

**Query classification:** This is a GUIDELINE query (not a research question). The system knows to route primarily to society guideline documents, not individual trials.

### Step 2: What Search Queries OpenEvidence Likely Executed

Based on the entities extracted, the retrieval system likely generated these parallel sub-queries:

1. **Primary guideline search:** `"IDSA" "SHEA" "Clostridioides difficile" guideline 2021` — This targets the specific guideline document. The system knows IDSA/SHEA published a focused update in 2021.

2. **Drug comparison search:** `fidaxomicin vancomycin "initial episode" CDI recurrence` — This finds the clinical trial data and meta-analyses comparing the two drugs.

3. **Meta-analysis search:** `fidaxomicin vancomycin meta-analysis recurrence rate Clostridioides difficile` — This finds pooled data to support quantitative claims.

4. **Supplementary guideline search:** `ACG CDI guidelines 2021` and `ASCRS CDI guidelines 2021` — These find corroborating society guidelines.

5. **Recent evidence search:** `CDI recurrence fidaxomicin 2024 2025` — This catches any newer evidence that might update the 2021 guideline.

### Step 3: Why OpenEvidence Selected These 5 Specific References

**Reference [1]: Johnson S et al. IDSA/SHEA 2021 CDI Guidelines. Clin Infect Dis 2021;73(5):e1029-e1044**
- **PMID:** 34164674
- **Why selected:** This is the EXACT guideline the user asked about. It is the PRIMARY authority source. The system matched "IDSA and SHEA guidelines" directly to this document. This paper was published September 2021 in Clinical Infectious Diseases, the official IDSA journal.
- **What OpenEvidence extracted:** The recommendation that fidaxomicin is preferred over vancomycin for initial non-fulminant CDI (conditional recommendation, moderate certainty). The specific dosage: fidaxomicin 200 mg orally twice daily for 10 days. The rationale about sustained clinical response and recurrence reduction.
- **Search keywords that would find this:** `IDSA SHEA 2021 CDI guideline focused update` — this is almost certainly a direct index hit, not a semantic search result.

**Reference [2]: Liao JX et al. Fidaxomicin vs Vancomycin Meta-Analysis. Pharmacotherapy 2022;42(11):810-827**
- **PMID:** 36223209
- **Why selected:** The user asked "how does it compare to vancomycin in terms of recurrence?" — this requires quantitative data. The guideline [1] states fidaxomicin is preferred but doesn't give pooled recurrence numbers. This meta-analysis provides the specific statistic: "risk ratio 0.69; 95% CI, 0.52–0.91" and the recurrence rates "16.1% for fidaxomicin versus 25.4% for vancomycin." OpenEvidence needed a source that QUANTIFIES the recurrence difference.
- **What OpenEvidence extracted:** The "approximately 31% reduction in recurrence" claim and the exact risk ratio. This is the ONLY source in the response that provides the pooled statistical comparison across 3,900+ patients.
- **Search keywords that would find this:** `fidaxomicin vancomycin meta-analysis recurrence systematic review` — this is a semantic match for "compare in terms of recurrence."

**Reference [3]: Kelly CR et al. ACG Clinical Guidelines for CDI. Am J Gastroenterol 2021;116(6):1124-1147**
- **PMID:** 34003176
- **Why selected:** This provides CORROBORATING guideline support. The system found that the American College of Gastroenterology also recommends fidaxomicin. This strengthens the claim by showing CONSENSUS across multiple societies, not just IDSA/SHEA.
- **What it contributed to the answer:** The sentence "Other professional societies, such as the American College of Gastroenterology...also recognize both fidaxomicin and vancomycin as first-line options, but highlight the superior sustained response." Also the cost consideration: "fidaxomicin's higher acquisition cost may limit its use."

**Reference [4]: Poylin V et al. ASCRS CDI Guidelines. Dis Colon Rectum 2021;64(6):650-668**
- **PMID:** 33734127
- **Why selected:** Another corroborating society guideline (American Society of Colon and Rectal Surgeons). This shows cross-specialty consensus.
- **What it contributed:** Used alongside [3] to support the "Other professional societies" claim. The system recognized that multiple societies reaching the same conclusion is stronger evidence than a single guideline.

**Reference [5]: van Prehn J et al. Recurrent CDI. JAMA 2025**
- **PMID:** Recent 2025 publication
- **Why selected:** This is the RECENCY signal. The system applied temporal weighting to find the most recent high-impact publication on CDI recurrence. A 2025 JAMA paper on recurrent CDI adds temporal freshness — it signals that the recommendation hasn't changed and remains current.
- **What it contributed:** Validates that the 2021 guideline recommendations are still the current standard in 2025.

### Step 4: How OpenEvidence Structured the Answer

The response has a distinctive two-part structure:

**Part 1 — "Practice Guideline" section:** This answers the question directly using ONLY the guideline [1]. Every claim in this section cites [1]. The system is saying: "Here is what the specific guideline you asked about says."

**Part 2 — "Building on..." synthesis section:** This expands beyond the single guideline to provide the full evidence landscape. It introduces the meta-analysis [2] for quantitative support, corroborating guidelines [3][4], and recent evidence [5].

This two-part structure is a deliberate design choice: guideline-first, then evidence-expansion. This matches how a physician thinks — "What does the guideline say?" followed by "What's the broader evidence?"

### Step 5: Claim-to-Source Mapping

| Claim in Answer | Source | Why This Source Supports It |
|---|---|---|
| "IDSA and SHEA recommend fidaxomicin as preferred first-line treatment" | [1] | Direct extraction from guideline recommendation |
| "Conditional recommendation and moderate certainty of evidence" | [1] | GRADE assessment language from the guideline |
| "Fidaxomicin 200 mg orally twice daily for 10 days" | [1] | Dosing recommendation from guideline Table 1 |
| "Vancomycin remains an acceptable alternative" | [1] | Explicit statement in guideline |
| "Fidaxomicin reduced recurrence by approximately 31% (RR 0.69, 95% CI 0.52–0.91)" | [2] | Pooled meta-analysis result — this specific number exists only in Liao et al. |
| "Recurrence rates of 16.1% for fidaxomicin versus 25.4% for vancomycin" | [2] | Absolute recurrence rates from meta-analysis |
| "Other professional societies...also recognize both as first-line options" | [3][4] | Corroborating guideline consensus |
| "Cost and access remain practical considerations" | [3] | ACG guideline explicitly discusses cost barriers |

### Step 6: What This Reveals About OpenEvidence's Architecture

1. **Guideline detection is a first-class routing signal.** When the query names a specific guideline ("IDSA and SHEA"), the system retrieves that exact document first. This is not a generic PubMed search — it's likely a direct index lookup.

2. **The system synthesizes across evidence tiers.** It doesn't just retrieve the guideline. It ALSO finds: (a) the quantitative evidence the guideline is based on, (b) corroborating guidelines from other societies, and (c) the most recent publication to validate temporal currency.

3. **Numerical claims are traced to specific sources.** The "31% reduction" and "RR 0.69" come specifically from [2], not from [1]. The guideline itself doesn't state pooled recurrence rates this precisely. OpenEvidence found a meta-analysis that QUANTIFIES what the guideline RECOMMENDS.

4. **The follow-up question is algorithmically generated.** "Would you like me to summarize the latest cost-effectiveness analyses..." — this is a query expansion suggestion based on detecting "cost" as an unresolved subtopic in the response.

---

## Analysis 2: MEDIUM — Apixaban vs Rivaroxaban in AF with CKD (Question 4)

### The Query
> "Compare apixaban and rivaroxaban for stroke prevention in non-valvular atrial fibrillation, focusing on efficacy, major bleeding risk, and key differences in patients with moderate chronic kidney disease (eGFR 30–50 mL/min)."

### Step 1: Query Decomposition

This is significantly more complex than Question 1. The system must handle:

**Multi-dimensional comparison:**
- Drug A (apixaban) vs Drug B (rivaroxaban)
- Across 3 outcomes: efficacy, major bleeding, CKD-specific differences
- In a specific subpopulation: moderate CKD (eGFR 30–50)

**PICO extraction:**
- P: Adults with non-valvular AF AND moderate CKD (eGFR 30–50 mL/min)
- I: Apixaban
- C: Rivaroxaban
- O: Stroke prevention efficacy, major bleeding risk, dosing differences

**Query classification:** RESEARCH QUESTION (comparative effectiveness). This requires guidelines + trial data + real-world evidence + pharmacokinetic data.

### Step 2: Probable Search Queries

The system likely generated 5-7 parallel sub-queries:

1. `ACC AHA atrial fibrillation guidelines 2023 DOAC anticoagulation` — Find the governing guideline
2. `apixaban rivaroxaban comparison atrial fibrillation meta-analysis` — Head-to-head comparison
3. `apixaban rivaroxaban bleeding risk comparison real-world` — Safety comparison
4. `apixaban rivaroxaban chronic kidney disease CKD eGFR` — CKD-specific subgroup data
5. `DOAC renal dosing CKD atrial fibrillation pharmacokinetics` — Pharmacokinetic data for dose adjustments
6. `apixaban vs rivaroxaban CKD stage 3 outcomes` — Specific to the eGFR range requested

### Step 3: Why These 9 Specific References Were Selected

**Reference [1]: 2023 ACC/AHA/ACCP/HRS AF Guideline. JACC 2024;83(1):109-279**
- **Why:** This is THE governing guideline for AF management in the US. Published 2024, it's the most current authority. The system identified this as the PRIMARY source because the query is fundamentally about clinical decision-making in AF.
- **What it contributed:** The recommendation that both apixaban and rivaroxaban are effective DOACs, but apixaban is associated with lower bleeding risk. The guideline's specific statements about CKD management.

**References [2]-[6]: Five separate comparative studies**
- [2] Lau WCY et al. **Multinational cohort** (Ann Intern Med 2022) — Selected because it provides MULTINATIONAL real-world data, not just US trial data
- [3] Mamas MA et al. **Meta-analysis** (Am J Cardiol 2022) — Selected because it POOLS the data: "HR 0.62 for major bleeding" and "HR 0.88 for stroke/embolism"
- [4] Ray WA et al. **Large US cohort** (JAMA 2021) — Selected because JAMA carries high authority and this is a major US dataset
- [5] Fralick M et al. **Routine practice cohort** (Ann Intern Med 2020) — Selected because it reflects REAL-WORLD (not trial) outcomes
- [6] Zhu W et al. **Stroke-specific analysis** (Stroke 2021) — Selected for the specific STROKE outcome

**References [7]-[9]: CKD-specific pharmacology**
- [7] Lau YC et al. AF + CKD review (JACC 2016) — Provides the pharmacokinetic data: "apixaban has approximately 25% renal excretion vs rivaroxaban approximately 36%"
- [8] Chan KE et al. DOACs in advanced CKD (JACC 2016) — CKD-specific dosing data
- [9] Kumar S et al. Anticoagulation in CKD review (JACC 2019) — Dosing adjustment details

### Step 4: The Retrieval Strategy Difference from Question 1

For Question 1 (easy), the system found ONE guideline and SUPPORTED it. For Question 4 (medium), the system needed to:

1. **Find the governing guideline** [1] — to establish what IS recommended
2. **Find the comparative evidence** [2-6] — because no head-to-head RCT exists between apixaban and rivaroxaban. The system recognized this and retrieved INDIRECT comparisons and real-world cohort studies instead.
3. **Find CKD-specific pharmacology** [7-9] — because the user asked specifically about eGFR 30-50, which requires pharmacokinetic reasoning (renal excretion percentages, dose adjustments)

This is a THREE-LAYER retrieval strategy: authority → evidence → subgroup. The system understands that for comparative effectiveness questions without head-to-head trials, you need meta-analyses and real-world evidence.

### Step 5: How the Answer Was Synthesized

The response makes a SYNTHESIZED CONCLUSION that doesn't appear verbatim in any single source: "apixaban is favored over rivaroxaban for stroke prevention in patients with non-valvular atrial fibrillation and moderate CKD due to a lower risk of major bleeding with similar efficacy."

This conclusion is CONSTRUCTED from:
- Guideline [1] says both are acceptable, but apixaban has safety advantages
- Meta-analysis [3] quantifies the bleeding difference (HR 0.62)
- Pharmacokinetic data [7][8] explains WHY (less renal excretion)
- CKD subgroup data [2][5][6] confirms the bleeding advantage persists in CKD

No single paper makes this exact claim. The system SYNTHESIZED it from converging evidence across 9 sources. This is "Attribution Gradients" in action — the conclusion has multiple independent support vectors.

### Step 6: Why Specific Statistics Were Chosen

The response states: "HR 0.62, 95% CI 0.56–0.69 for major bleeding" and "HR 0.88, 95% CI 0.81–0.95 for stroke."

These specific numbers come from Reference [3] (Mamas et al. meta-analysis). The system chose THIS meta-analysis over others because:
- It's a meta-analysis (highest evidence tier for pooled data)
- It's specifically about apixaban vs rivaroxaban (not all DOACs)
- Published in American Journal of Cardiology (high impact)
- Provides BOTH efficacy AND safety HRs in one source

The system also states "apixaban has approximately 25% renal excretion" vs "rivaroxaban approximately 36%." These pharmacokinetic facts come from [7] and [8], which are JACC review articles on DOACs in CKD.

---

## Analysis 3: HARD — EGFR Exon 20 Insertion NSCLC (Question 7)

### The Query
> "In patients with metastatic non-small cell lung cancer, EGFR exon 20 insertion mutations, and no prior targeted therapy, how do current guidelines and key trials position amivantamab versus mobocertinib, including efficacy, toxicity, and sequencing with platinum-based chemotherapy and immunotherapy?"

### Step 1: Query Decomposition

This is the most complex query in the set. It requires:

**Multi-entity extraction:**
- Disease: Metastatic NSCLC
- Molecular subtype: EGFR exon 20 insertion mutations (rare variant, 1-10% of EGFR mutations)
- Treatment status: No prior targeted therapy (treatment-naive context)
- Drug A: Amivantamab (bispecific antibody, EGFR/MET)
- Drug B: Mobocertinib (oral TKI)
- Comparison dimensions: Efficacy, toxicity, sequencing
- Additional context: Platinum-based chemo, immunotherapy

**PICO extraction:**
- P: Treatment-naive metastatic NSCLC with EGFR exon 20 insertion
- I: Amivantamab
- C: Mobocertinib
- O: Efficacy (PFS, ORR), toxicity profile, optimal sequencing

**Query classification:** DEEP RESEARCH QUESTION. This requires guidelines + phase 3 trial data + indirect comparisons + toxicity analysis + sequencing recommendations.

### Step 2: The Search Strategy Was Multi-Phase

The system likely executed searches in waves:

**Wave 1 — Background context:**
- `EGFR exon 20 insertion mutations NSCLC biology resistance TKI` → [1][2][3]
- This retrieves papers explaining WHY exon 20 insertions are different (resistance to standard EGFR TKIs)

**Wave 2 — Current guidelines:**
- `ASCO guideline NSCLC EGFR driver alterations 2024` → [4]
- This finds the governing ASCO Living Guideline (version 2024.2)

**Wave 3 — Pivotal trials:**
- `PAPILLON trial amivantamab chemotherapy EGFR exon 20 NEJM` → [8]
- `EXCLAIM-2 mobocertinib first-line platinum chemotherapy` → [7]
- These are the TWO definitive phase 3 trials

**Wave 4 — Indirect comparisons:**
- `amivantamab mobocertinib indirect comparison matching adjusted` → [9][10][11]
- Since no head-to-head trial exists, the system finds matching-adjusted indirect comparisons (MAICs)

**Wave 5 — Safety/toxicity:**
- `amivantamab adverse events infusion reaction rash CHRYSALIS` → [12][13]
- `mobocertinib diarrhea QTc prolongation safety` → [6]

### Step 3: Why These 14 References — And Why So Many

This question required 14 references (vs 5 for Question 1) because:

1. **There is no single authoritative source.** Unlike CDI (one clear guideline), EGFR exon 20 insertions are a rapidly evolving field. The ASCO guideline [4] provides direction, but the key evidence emerged from trials published 2021-2025.

2. **Two separate drug programs need independent evidence.** Amivantamab (Janssen) and mobocertinib (Takeda) were developed by different companies, studied in different trials, and have fundamentally different mechanisms (bispecific antibody vs oral TKI).

3. **No head-to-head comparison exists.** The system had to find indirect comparisons [9][10][11] to address the "versus" part of the query.

### Step 4: The Critical Trial References

**Reference [8]: Zhou C et al. PAPILLON trial. NEJM 2023;389(22):2039-2051**
- **PMID:** 37870976
- **Why this is the anchor reference:** This is the PIVOTAL Phase 3 trial that established amivantamab + chemotherapy as first-line standard of care. Published in NEJM (highest impact), it showed median PFS of 11.4 months vs 6.7 months for chemo alone (HR 0.40, P<0.001).
- **Search keywords:** `PAPILLON amivantamab EGFR exon 20 phase 3 first-line NEJM`
- **What the system extracted:** The PFS numbers (11.4 vs 6.7 months), the hazard ratio (0.40), the ORR (73% vs 47%), and the fact that this led to FDA approval for first-line use.

**Reference [7]: Jänne PA et al. EXCLAIM-2 trial. JCO 2025;43(13):1553-1563**
- **PMID:** 39879577
- **Why critical:** This is the NEGATIVE result — mobocertinib FAILED to beat chemotherapy in the first-line setting. The system selected this specifically to answer "how do guidelines position mobocertinib" — the answer is: NOT as first-line, because EXCLAIM-2 crossed the futility boundary.
- **Search keywords:** `EXCLAIM-2 mobocertinib first-line EGFR exon 20 JCO`
- **Key data extracted:** Median PFS 9.6 months for BOTH arms (HR 1.04), meaning mobocertinib was NOT superior to chemo. This is why the answer states "mobocertinib is not currently recommended as first-line therapy."
- **Temporal note:** This paper was published January 2025, making it one of the most recent references. The system's temporal weighting correctly prioritized this recent definitive trial result.

### Step 5: How OpenEvidence Handled the "Sequencing" Sub-Question

The user asked about "sequencing with platinum-based chemotherapy and immunotherapy." The system needed to address three sequencing scenarios:

1. **First-line:** Amivantamab + chemo (supported by PAPILLON [8])
2. **Second-line after chemo:** Amivantamab monotherapy or mobocertinib (supported by CHRYSALIS [13] and phase 1/2 mobocertinib data [14])
3. **Immunotherapy:** NOT recommended in EGFR-mutant NSCLC (supported by ASCO guideline [4])

The answer explicitly states: "Immunotherapy (PD-1/PD-L1 inhibitors) has limited efficacy in this molecular subset and is not recommended as monotherapy or in combination with chemotherapy in EGFR-mutant NSCLC."

This claim is supported by [4] (ASCO guideline) and [14] (Zhou et al. phase 1/2 data showing poor IO outcomes). The system understood that the user asking about immunotherapy sequencing needed a NEGATIVE answer — IO doesn't work here.

### Step 6: The Indirect Comparison Strategy

Since no head-to-head trial compares amivantamab to mobocertinib directly, the system found THREE matching-adjusted indirect comparisons:

- [9] Kim TM et al. Matching-adjusted comparison, platinum-pretreated (Future Oncol 2024)
- [10] Ou SI et al. Indirect treatment comparison, platinum-pretreated (Clin Lung Cancer 2024)
- [11] Russell MC et al. Pharmacology comparison (Ann Pharmacother 2023)

These papers apply statistical methods (MAIC, Bucher ITC) to compare outcomes across different trials. The system recognized that when no RCT exists, MAICs are the next best evidence for "Drug A vs Drug B" questions.

### Step 7: Claim-Level Attribution Map

| Claim | Source | Retrieval Signal |
|---|---|---|
| "EGFR exon 20 insertions account for 1-10% of EGFR mutations" | [1][2][3] | Background prevalence data from review articles |
| "Confer intrinsic resistance to conventional EGFR TKIs" | [1][2][3] | Molecular biology explaining why these mutations are different |
| "ASCO 2024.2 recommends first-line amivantamab + platinum-pemetrexed" | [4] | Direct guideline extraction |
| "Median PFS 11.4 months vs 6.7 months (HR 0.40)" | [8] | PAPILLON trial primary endpoint |
| "Mobocertinib did not improve PFS vs chemotherapy (HR 1.04)" | [7] | EXCLAIM-2 negative result |
| "Infusion-related reactions (66%), rash (86%), paronychia (45%)" | [12][13] | FDA approval summary + CHRYSALIS safety data |
| "Diarrhea up to 93%, QTc prolongation risk" | [6] | Mobocertinib adverse event characterization paper |
| "Amivantamab has more favorable safety profile than mobocertinib" | [9][10][11] | Synthesized from indirect comparisons |
| "Immunotherapy has limited efficacy in this subset" | [4][14] | Guideline + trial data on IO inefficacy |

### Step 8: What This Reveals About OpenEvidence's Deep Processing

1. **The system handles NEGATIVE evidence.** It didn't just find papers supporting amivantamab. It found the EXCLAIM-2 failure [7] for mobocertinib and used it to construct a sequencing recommendation. This requires understanding that a failed trial is evidence AGAINST a particular positioning.

2. **Temporal awareness is critical here.** The EXCLAIM-2 results [7] were published January 2025. The ASCO 2024.2 guideline [4] was published before EXCLAIM-2 was formally published. The system correctly prioritized the newest trial data even when it post-dates the guideline.

3. **The system understands drug mechanisms.** It distinguished amivantamab (bispecific antibody, IV) from mobocertinib (oral TKI) and correctly attributed different toxicity profiles to their different mechanisms of action. This isn't just keyword matching — it's mechanistic understanding.

4. **14 references = maximum retrieval depth.** This response required the most sources of any in the benchmark set, reflecting the complexity of synthesizing across: biology reviews, guidelines, two separate phase 3 trials, three indirect comparisons, two safety analyses, and an FDA approval summary.

---

## Cross-Question Architectural Insights

### What We Can Confirm About OpenEvidence's Architecture

| Architecture Element | Evidence From These 3 Queries |
|---|---|
| **Query decomposition into PICO** | All 3 queries show evidence of structured entity extraction before retrieval |
| **Guideline-first routing** | When a guideline is named (Q1, Q4), it's ALWAYS the first reference. For Q7, the ASCO guideline is [4] because background context [1-3] was needed first |
| **Multi-source synthesis** | Q1: 5 refs. Q4: 9 refs. Q7: 14 refs. Complexity scales with query complexity |
| **Two-part answer structure** | "Practice Guideline" section (direct answer) + "Building on..." section (evidence expansion) — consistent across all queries |
| **Temporal weighting** | Q1 includes a 2025 JAMA paper. Q7 includes the January 2025 EXCLAIM-2 trial. The system prioritizes recent evidence |
| **Indirect comparison retrieval** | When no head-to-head trial exists (Q4, Q7), the system finds MAICs and real-world cohort comparisons |
| **Negative evidence handling** | Q7 uses EXCLAIM-2's FAILURE to position mobocertinib as NOT first-line — the system understands negative results |
| **Follow-up question generation** | Every response ends with a suggested follow-up. These are likely generated by detecting unaddressed aspects of the query space |
| **Claim-level citation** | Every factual claim has at least one citation. Statistics ALWAYS have citations. Synthesis conclusions cite multiple sources |

### What Hunt AI Must Replicate

For Hunt AI to match this quality, the RAG pipeline must:

1. **Route guideline queries to pre-indexed guideline documents** — not general PubMed search
2. **Execute parallel sub-queries** for different aspects of complex questions (efficacy, safety, dosing, CKD-specific)
3. **Find quantitative evidence** beyond the guideline itself — guidelines RECOMMEND, meta-analyses QUANTIFY
4. **Handle the "no head-to-head trial" scenario** by retrieving indirect comparisons and real-world cohort data
5. **Apply temporal weighting** to prefer 2024-2025 evidence over older data, while still citing foundational guidelines
6. **Synthesize across evidence tiers** — not just retrieve and concatenate, but BUILD a conclusion from converging evidence
7. **Verify every numerical claim** maps to a specific source span (the "31% reduction" must trace to Liao et al.'s meta-analysis, not be hallucinated)

### The Key Difference Between OpenEvidence and What Hunt AI Can Do

OpenEvidence has FULL-TEXT access to NEJM, JAMA, Lancet, and other paywalled journals. This means when it retrieves the PAPILLON trial [8], it can read the entire methods section, results tables, and supplementary data.

Hunt AI will have PubMed ABSTRACTS only for most paywalled papers, plus PMC Open Access full-text for about 3M articles. This means:
- For guideline documents (often freely available as PDFs), Hunt AI can match OpenEvidence
- For major trial results, Hunt AI must extract key statistics from abstracts (which usually contain PFS, HR, ORR in the abstract)
- For pharmacokinetic details and subgroup analyses, Hunt AI may miss information that's only in the full text

The mitigation: use Tavily to find trial result summaries on journal websites, ASCO Post, and cancer network sites, which often quote key statistics from the full text in freely accessible news articles.
