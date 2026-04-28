# OpenEvidence Gold Standard — 10 Benchmark Queries

This file contains the 10 benchmark queries and their OpenEvidence gold-standard answers. Every Noocyte AI response is evaluated against this standard.

**How to use this file:**
- The `eval-benchmark` skill uses these as the scoring reference
- The `system-prompter` agent uses these to test every prompt change
- The `ml-model-optimizer` skill uses these to measure pipeline improvements
- The `brainstormer` agent uses these to understand the quality bar Noocyte AI must meet or exceed

---

## What Makes These Answers Excellent

Before reading the answers, understand what OpenEvidence does that Noocyte AI must replicate:

1. **BLUF structure** — The direct answer is in the first sentence, never buried
2. **Quantified evidence** — Every comparison has numbers (%, HR, NNT, CI)
3. **Guideline hierarchy** — Specific guideline body + year + recommendation strength
4. **Inline citations** — Every factual claim has a numbered reference
5. **Alternatives** — Always mentions what to do when first-line is unavailable
6. **Implicit follow-up** — The answer naturally invites the next question

Noocyte AI must match this quality AND add:
- India-specific context (ICMR priority, drug availability, pricing)
- Explicit `follow_up_question` field
- WhatsApp-optimised formatting

---

## Query 1 (Easy): First-line CDI Treatment

**Query:** "What is the first-line treatment for Clostridioides difficile infection?"

**OpenEvidence Gold Standard:**
Fidaxomicin (200 mg orally twice daily for 10 days) is preferred over vancomycin for initial non-fulminant CDI per IDSA/SHEA 2021 guidelines (strong recommendation, moderate evidence). Fidaxomicin demonstrates significantly lower recurrence rates compared to vancomycin (16% vs 25%; RR 0.64, 95% CI 0.53–0.78) based on the MODIFY I and MODIFY II trials. Vancomycin (125 mg orally four times daily for 10 days) remains an acceptable alternative when fidaxomicin is unavailable or cost-prohibitive. Metronidazole is no longer recommended as first-line therapy due to inferior outcomes.

**Key elements Noocyte AI must include:**
- Fidaxomicin as first-line
- Specific dose (200mg BD × 10 days)
- Recurrence rate comparison (16% vs 25%)
- MODIFY I/II trial reference
- IDSA/SHEA 2021 citation
- Vancomycin as acceptable alternative

**India-specific addition Noocyte AI should include:**
- Fidaxomicin availability in India (limited, expensive)
- Vancomycin oral formulation availability
- Note that metronidazole is still widely used in India despite guideline change

---

## Query 2 (Easy): Anticoagulation in AF with CKD

**Query:** "What anticoagulation should I use for atrial fibrillation in a patient with CKD stage 3b (eGFR 35)?"

**OpenEvidence Gold Standard:**
Apixaban is the preferred DOAC for AF with CKD stage 3b (eGFR 30–49 mL/min/1.73m²), based on consistent evidence of superior safety compared to warfarin and other DOACs. The ARISTOTLE trial demonstrated a 21% relative risk reduction in stroke/systemic embolism (HR 0.79, 95% CI 0.66–0.95) and 31% reduction in major bleeding (HR 0.69, 95% CI 0.60–0.80) versus warfarin. Dose reduction to apixaban 2.5 mg twice daily is required if the patient meets ≥2 of: age ≥80, weight ≤60 kg, serum creatinine ≥1.5 mg/dL. Rivaroxaban and dabigatran require more significant dose adjustments and have less favourable safety profiles at this eGFR level. Warfarin remains an option but requires careful INR monitoring given altered pharmacokinetics in CKD.

**Key elements Noocyte AI must include:**
- Apixaban as preferred DOAC
- eGFR range specification (30–49)
- ARISTOTLE trial data (HR 0.79, HR 0.69)
- Dose reduction criteria (2 of 3 criteria)
- Comparison with rivaroxaban/dabigatran

---

## Query 3 (Easy): HbA1c Target in Elderly T2DM

**Query:** "What is the appropriate HbA1c target for an elderly patient with type 2 diabetes?"

**OpenEvidence Gold Standard:**
The ADA 2024 Standards of Care recommend individualised HbA1c targets for older adults with T2DM based on functional status and comorbidity burden. For healthy older adults with few comorbidities and intact cognitive function, an HbA1c target of <7.0–7.5% is appropriate. For those with multiple chronic conditions, cognitive impairment, or limited life expectancy, a less stringent target of <8.0% is recommended to minimise hypoglycaemia risk. The ACCORD trial demonstrated increased mortality with intensive glycaemic control (HbA1c <6.0%) in high-risk patients, reinforcing the importance of individualisation. Agents with low hypoglycaemia risk (metformin, DPP-4 inhibitors, SGLT2 inhibitors, GLP-1 RAs) are preferred over sulfonylureas and insulin in this population.

**Key elements Noocyte AI must include:**
- ADA 2024 citation
- Healthy elderly: <7.0–7.5%
- Frail/comorbid: <8.0%
- ACCORD trial reference
- Drug preference (low hypoglycaemia risk agents)

---

## Query 4 (Medium): SGLT2 Inhibitor in HFrEF

**Query:** "Which SGLT2 inhibitor should I use for heart failure with reduced ejection fraction?"

**OpenEvidence Gold Standard:**
Both empagliflozin and dapagliflozin are Class I recommendations (Level A evidence) for HFrEF per ESC 2021 and ACC/AHA 2022 guidelines, with equivalent efficacy demonstrated in landmark trials. The EMPEROR-Reduced trial (empagliflozin) showed a 25% reduction in the composite of CV death or HF hospitalisation (HR 0.75, 95% CI 0.65–0.86), while DAPA-HF (dapagliflozin) demonstrated a 26% reduction (HR 0.74, 95% CI 0.65–0.85). Both agents reduce HF hospitalisations by approximately 30% and are effective regardless of diabetes status. Choice between agents is primarily driven by cost, availability, and patient preference, as no head-to-head trial exists. Both are initiated at standard doses (empagliflozin 10 mg once daily; dapagliflozin 10 mg once daily) and can be used down to eGFR 20 mL/min/1.73m² for HF benefit.

**Key elements Noocyte AI must include:**
- Both empagliflozin and dapagliflozin as Class I
- EMPEROR-Reduced (HR 0.75) and DAPA-HF (HR 0.74) data
- Effective regardless of diabetes status
- eGFR threshold (20 for HF benefit)
- No head-to-head trial

---

## Query 5 (Medium): Statin for Primary Prevention

**Query:** "Should I start a statin for primary prevention in a 55-year-old with a 12% 10-year ASCVD risk?"

**OpenEvidence Gold Standard:**
A 12% 10-year ASCVD risk falls in the intermediate risk category (7.5–20%) per ACC/AHA 2019 Cholesterol Guidelines, where statin therapy is a Class IIa recommendation (reasonable to initiate). Moderate-intensity statin therapy (e.g., atorvastatin 10–20 mg or rosuvastatin 5–10 mg daily) is appropriate for this risk level, targeting ≥30–49% LDL-C reduction. The decision should incorporate a clinician-patient risk discussion weighing absolute risk reduction (NNT approximately 50–100 over 10 years), potential adverse effects, patient preferences, and risk-enhancing factors (family history, high-sensitivity CRP, coronary artery calcium score). A coronary artery calcium (CAC) score of 0 may support deferring statin therapy, while CAC ≥100 Agatston units supports initiating treatment. Lifestyle modification remains foundational regardless of statin decision.

**Key elements Noocyte AI must include:**
- Intermediate risk classification (7.5–20%)
- Class IIa recommendation
- Moderate-intensity statin examples and doses
- NNT (50–100 over 10 years)
- CAC score as decision aid
- Shared decision-making emphasis

---

## Query 6 (Medium): DAPT Duration After DES

**Query:** "How long should dual antiplatelet therapy be continued after a drug-eluting stent for stable CAD?"

**OpenEvidence Gold Standard:**
Per ESC 2023 guidelines, 6 months of DAPT (aspirin + P2Y12 inhibitor) is the standard recommendation following DES implantation for stable CAD (Class I, Level A). Shorter DAPT duration (1–3 months) followed by P2Y12 inhibitor monotherapy may be considered in patients with high bleeding risk (HBR) using the ARC-HBR criteria, supported by the MASTER DAPT and STOPDAPT-2 trials. Extended DAPT beyond 12 months may be considered in patients with high ischaemic risk and low bleeding risk, using the DAPT score to guide decision-making (score ≥2 favours extension). Clopidogrel is the preferred P2Y12 inhibitor for stable CAD; ticagrelor and prasugrel are reserved for ACS presentations. Proton pump inhibitor co-prescription is recommended for patients at increased GI bleeding risk.

**Key elements Noocyte AI must include:**
- 6 months as standard (ESC 2023)
- HBR criteria and shorter DAPT option
- MASTER DAPT and STOPDAPT-2 references
- DAPT score for extension decisions
- Clopidogrel preferred for stable CAD

---

## Query 7 (Hard, India-Specific): MDR-TB in India

**Query:** "What does ICMR recommend for MDR-TB treatment in India?"

**OpenEvidence Gold Standard:**
The ICMR and India's PMDT (Programmatic Management of Drug-resistant Tuberculosis) programme recommends the BPaL regimen (bedaquiline + pretomanid + linezolid) as the preferred treatment for MDR-TB and pre-XDR-TB, aligned with WHO 2022 consolidated guidelines. The ZeNix trial demonstrated 89% favourable outcomes with BPaL at 26 weeks, superior to the previous longer regimens. The standard BPaL duration is 26 weeks (6 months). Bedaquiline (400 mg daily × 2 weeks, then 200 mg three times weekly × 22 weeks) is available free of charge under the PMDT programme at designated DR-TB centres. Linezolid dose optimisation (600 mg → 300 mg) is recommended to reduce haematological toxicity while maintaining efficacy. Cardiac monitoring (QTc) is mandatory with bedaquiline.

**Key elements Noocyte AI must include:**
- BPaL regimen (bedaquiline + pretomanid + linezolid)
- ICMR/PMDT reference
- ZeNix trial (89% favourable outcomes)
- 26-week duration
- Free availability under PMDT
- QTc monitoring requirement

---

## Query 8 (Hard): Apixaban vs Rivaroxaban in AF with CKD

**Query:** "Between apixaban and rivaroxaban, which is preferred for atrial fibrillation with moderate CKD (eGFR 30–50)?"

**OpenEvidence Gold Standard:**
Apixaban is preferred over rivaroxaban for AF with moderate CKD (eGFR 30–50 mL/min/1.73m²) based on superior safety data and pharmacokinetic profile. Apixaban has the lowest renal elimination of all DOACs (27%), compared to rivaroxaban (33%), resulting in less drug accumulation in CKD. The ARISTOTLE trial demonstrated lower major bleeding with apixaban versus warfarin (HR 0.69), and observational data consistently show apixaban's favourable safety profile in CKD. Rivaroxaban's once-daily dosing and higher renal clearance increase bleeding risk as eGFR declines. Both agents are contraindicated when eGFR <15 mL/min/1.73m². Dose reduction criteria for apixaban (2.5 mg BD if ≥2 of: age ≥80, weight ≤60 kg, creatinine ≥1.5 mg/dL) should be applied carefully in CKD patients.

**Key elements Noocyte AI must include:**
- Apixaban preferred
- Renal elimination comparison (27% vs 33%)
- ARISTOTLE HR 0.69
- Contraindication at eGFR <15
- Dose reduction criteria

---

## Query 9 (Hard): Fidaxomicin vs Vancomycin for Recurrent CDI

**Query:** "What does the evidence show for fidaxomicin versus vancomycin in recurrent CDI?"

**OpenEvidence Gold Standard:**
Fidaxomicin is strongly preferred over vancomycin for recurrent CDI based on superior efficacy in reducing further recurrence. The MODIFY I and MODIFY II trials demonstrated that fidaxomicin reduces recurrence by 36% relative to vancomycin (16% vs 25%; RR 0.64, 95% CI 0.53–0.78), with the benefit most pronounced in non-ribotype 027 strains. The mechanism of superiority relates to fidaxomicin's narrow spectrum activity (preserving Bacteroides and other colonisation-resistance organisms) compared to vancomycin's broader disruption of the gut microbiome. For patients with multiple recurrences (≥3 episodes), bezlotoxumab (a monoclonal antibody against C. difficile toxin B) added to standard antibiotic therapy further reduces recurrence by 40% (MODIFY I/II: RR 0.60). Fidaxomicin's higher cost (approximately 10–20× vancomycin) remains a barrier in resource-limited settings.

**Key elements Noocyte AI must include:**
- Fidaxomicin preferred for recurrent CDI
- 16% vs 25% recurrence (RR 0.64)
- MODIFY I/II citation
- Mechanism (narrow spectrum, microbiome preservation)
- Bezlotoxumab for ≥3 recurrences
- Cost consideration

---

## Query 10 (Hard, India-Specific): Dolo 650 for Fever

**Query:** "What is the evidence for Dolo 650 for fever management and what is the appropriate dosing?"

**OpenEvidence Gold Standard:**
Paracetamol (Dolo 650, acetaminophen) 650 mg is an appropriate and widely used antipyretic for fever management in adults, supported by extensive evidence and WHO Essential Medicines List inclusion. For fever in adults, the recommended dose is 500–1000 mg every 4–6 hours as needed, with a maximum daily dose of 4000 mg (4 g/day) in healthy adults and 2000 mg/day in patients with hepatic impairment or chronic alcohol use. The 650 mg formulation (Dolo 650) is particularly popular in India for its balance of efficacy and tolerability. Paracetamol is preferred over NSAIDs (ibuprofen, diclofenac) in patients with peptic ulcer disease, renal impairment, or those on anticoagulants. Combination products containing paracetamol (Combiflam, Dolo-BE) must be accounted for to avoid inadvertent overdose exceeding the 4 g/day limit.

**Key elements Noocyte AI must include:**
- INN resolution: Paracetamol (Dolo 650)
- Dose: 500–1000mg every 4–6 hours
- Maximum: 4g/day (healthy), 2g/day (hepatic impairment)
- NSAID comparison and when to prefer paracetamol
- Combination product warning (Combiflam)
- India-specific context (Dolo 650 popularity, pricing)

---

## Scoring Reference

A Noocyte AI response passes a benchmark query if it scores ≥ 4/5 on the rubric:

| Dimension | Weight | Pass Condition |
|-----------|--------|---------------|
| Key elements present | 1 | ≥ 75% of listed key elements appear in the answer |
| Citation quality | 1 | ≥ 2 inline citations with DOIs |
| No prescriptive language | 1 | Zero prohibited phrases |
| India context (India-specific queries only) | 1 | ICMR/India reference present |
| Confidence level present | 1 | HIGH, MEDIUM, or LOW stated |

**Sprint gates:**
- Week 1: ≥ 4/10 passing
- Week 2: ≥ 5/10 passing
- Week 3: ≥ 7/10 passing
- Week 4: ≥ 9/10 passing
