# Hunt AI: Medical Knowledge Graph & Retrieval Routing Guide

## Purpose

This document is the foundational knowledge map for Hunt AI's query routing system. It defines which publications to prioritize for each medical specialty, how to use PubMed effectively, all medical specialties with descriptions for system prompt engineering, and demographic-specific considerations for accurate evidence retrieval.

---

# PART 1: PubMed Search Optimization for Hunt AI

## 1.1 PubMed Architecture — What Hunt AI Must Know

PubMed contains two distinct databases that behave differently:

**MEDLINE** (~28M citations): Fully indexed with MeSH (Medical Subject Headings) terms by human indexers. MeSH enables precise filtering by species (Humans vs Animals), sex (Male/Female), age groups, and study type. These are the gold-standard indexed articles.

**Non-MEDLINE PubMed** (~8M citations): Includes preprints, author manuscripts, and articles from journals not indexed for MEDLINE. These have NO MeSH terms, so MeSH-based filters will MISS them.

**Hunt AI implication:** Always search BOTH — use MeSH for precision on indexed articles AND title/abstract keyword search for non-indexed articles. The "Master Search Formula" combines both:
```
(MeSH_search AND Humans[MeSH]) OR (keyword_search NOT medline[sb])
```

## 1.2 Critical PubMed Filters for Hunt AI

### Species Filters
- `Humans[MeSH]` — Restrict to human studies (CRITICAL for clinical queries)
- To properly exclude animal-only studies, use the double-negative approach:
  `NOT (animals[MeSH] NOT humans[MeSH])` — This keeps studies that are BOTH human and animal while removing animal-only studies.

### Sex Filters
- `Male[MeSH]` — Studies involving male subjects
- `Female[MeSH]` — Studies involving female subjects
- These are MeSH-based, so they only work on MEDLINE-indexed articles.

### Age Group Filters (MeSH Terms)
| PubMed Filter | MeSH Term | Age Range |
|---|---|---|
| Newborn | Infant, Newborn | Birth to 1 month |
| Infant | Infant | Birth to 23 months |
| Child, Preschool | Child, Preschool | 2-5 years |
| Child | Child | 6-12 years |
| Adolescent | Adolescent | 13-18 years |
| Young Adult | Young Adult | 19-24 years |
| Adult | Adult | 19-44 years |
| Middle Aged | Middle Aged | 45-64 years |
| Aged | Aged | 65-79 years |
| Aged, 80 and over | Aged, 80 and over | 80+ years |

### Study Type Filters
| Filter | Use Case | PubMed Tag |
|---|---|---|
| Clinical Trial | Drug efficacy/safety questions | `Clinical Trial[pt]` |
| Randomized Controlled Trial | Highest-evidence therapy questions | `Randomized Controlled Trial[pt]` |
| Meta-Analysis | Pooled evidence for comparisons | `Meta-Analysis[pt]` |
| Systematic Review | Comprehensive evidence summaries | `systematic[sb]` |
| Practice Guideline | What guidelines recommend | `Practice Guideline[pt]` |
| Review | General topic overviews | `Review[pt]` |
| Case Reports | Rare conditions, unusual presentations | `Case Reports[pt]` |

### Clinical Queries (Pre-built Search Strategies)
PubMed's Clinical Queries apply validated search hedges for specific clinical categories:
- **Therapy** — Finds RCTs, controlled trials (default)
- **Diagnosis** — Finds studies on diagnostic accuracy (sensitivity/specificity)
- **Prognosis** — Finds cohort studies, follow-up studies
- **Etiology** — Finds cohort studies examining causation/risk
- **Clinical Prediction Guides** — Finds prediction rules/models

Each has two modes:
- **Broad/Sensitive** — Casts a wide net, retrieves more but includes noise
- **Narrow/Specific** — Highly targeted, misses some relevant articles

**Hunt AI strategy:** Use Narrow/Specific for guideline queries (precision matters). Use Broad/Sensitive for research questions (recall matters).

## 1.3 Too Many Results vs Too Few Results

### When Results Are Too Many (>500 hits)
1. Add MeSH terms with `[Majr]` (Major Topic) restriction — only retrieves articles where this is the PRIMARY focus
2. Narrow date range: add `AND ("2023"[PDAT] : "2026"[PDAT])`
3. Add study type filter: `AND (Meta-Analysis[pt] OR systematic[sb])`
4. Add specific subheadings: `"Diabetes Mellitus, Type 2/drug therapy"[MeSH]`
5. Filter to core clinical journals using Abridged Index Medicus: `jsubsetaim[text]`

### When Results Are Too Few (<10 hits)
1. Remove MeSH restrictions — search title/abstract only: `[tiab]`
2. Add synonyms with OR: `(heart attack OR myocardial infarction OR STEMI)`
3. Explode MeSH terms (include narrower terms): default behavior, but verify
4. Remove date filters
5. Search the non-MEDLINE subset: add `NOT medline[sb]` to find preprints and unindexed articles
6. Use Related Citations feature to find similar articles

## 1.4 MeSH Strategies for Hunt AI's Query Router

When the Query Router identifies the specialty, it should append appropriate MeSH terms:

```python
SPECIALTY_MESH_MAP = {
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
}
```

---

# PART 2: Global Medical Publications — The "Ivy League" of Medical Journals

## 2.1 The "Big Four" General Medical Journals

These are the equivalent of Ivy League universities — every physician worldwide reads them. Any article from these journals should be weighted at the HIGHEST tier.

| Rank | Journal | Impact Factor (2024) | Publisher | Country | Readership | PubMed Abbreviation |
|------|---------|---------------------|-----------|---------|------------|---------------------|
| 1 | New England Journal of Medicine (NEJM) | 96.2 | Massachusetts Medical Society | USA | 600K+ physicians, 177 countries | N Engl J Med |
| 2 | The Lancet | 98.4 | Elsevier | UK | 1.8M registered users | Lancet |
| 3 | JAMA (Journal of the American Medical Association) | 63.1 | American Medical Association | USA | 1.2M email subscribers, most widely circulated | JAMA |
| 4 | BMJ (British Medical Journal) | 105.7 | BMJ Publishing Group | UK | Open access, global reach | BMJ |

**Additional Tier 1 General Journals:**

| Journal | Impact Factor | Publisher | Country | Notes |
|---------|--------------|-----------|---------|-------|
| Annals of Internal Medicine | 39.2 | American College of Physicians | USA | Top internal medicine journal |
| Nature Medicine | 58.7 | Springer Nature | UK | Translational research |
| JAMA Internal Medicine | 22.5 | AMA | USA | Internal medicine focus |
| PLOS Medicine | 15.8 | PLOS | USA | Open access |
| Cochrane Database of Systematic Reviews | 8.4 | Cochrane Collaboration | UK | Gold standard for systematic reviews |

## 2.2 Specialty Journals — The "Parent and Child" Hierarchy

### CARDIOLOGY (Heart & Vascular)
**Parent Society:** American Heart Association (AHA) + American College of Cardiology (ACC) + European Society of Cardiology (ESC)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Circulation | 35.5 | AHA | Flagship — all cardiovascular research |
| Parent | Journal of the American College of Cardiology (JACC) | 21.7 | ACC | Clinical cardiology, trials, guidelines |
| Parent | European Heart Journal | 37.6 | ESC | European cardiology, ESC guidelines |
| Child | Circulation Research | 16.5 | AHA | Basic/translational cardiovascular science |
| Child | JACC: Heart Failure | 10.3 | ACC | Heart failure-specific |
| Child | JACC: Cardiovascular Interventions | 9.5 | ACC | Interventional cardiology, PCI, TAVR |
| Child | JACC: Clinical Electrophysiology | 6.7 | ACC | Arrhythmias, devices, EP |
| Child | JACC: Cardiovascular Imaging | 12.8 | ACC | Cardiac imaging modalities |
| Child | Heart Rhythm | 5.7 | HRS | Electrophysiology society journal |
| Child | European Journal of Heart Failure | 16.9 | ESC/HFA | European HF research |
| Regional | Indian Heart Journal | 1.7 | Cardiological Society of India | Indian cardiology |

**Key guideline bodies:** AHA/ACC (US), ESC (Europe), Cardiological Society of India (CSI)
**Website:** heart.org (AHA), acc.org, escardio.org

### ONCOLOGY (Cancer)
**Parent Society:** American Society of Clinical Oncology (ASCO) + European Society for Medical Oncology (ESMO) + National Comprehensive Cancer Network (NCCN)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Journal of Clinical Oncology (JCO) | 44.8 | ASCO | Clinical trials, practice guidelines |
| Parent | Lancet Oncology | 41.6 | Elsevier | High-impact oncology trials |
| Parent | Annals of Oncology | 32.9 | ESMO | European oncology, ESMO guidelines |
| Child | JAMA Oncology | 28.4 | AMA | Clinical oncology |
| Child | Journal of the National Cancer Institute (JNCI) | 9.9 | Oxford | Cancer epidemiology, prevention |
| Child | Clinical Cancer Research | 10.0 | AACR | Translational oncology |
| Child | Cancer Discovery | 29.7 | AACR | Breakthrough research |
| Child | Nature Cancer | 22.7 | Springer Nature | High-impact cancer biology |
| Child | Cancer Cell | 48.8 | Cell Press | Cancer biology, mechanisms |
| Organ | Breast Cancer Research and Treatment | 3.0 | — | Breast cancer-specific |
| Organ | Lung Cancer | 4.0 | IASLC | Lung cancer-specific |
| Regional | Indian Journal of Cancer | 1.4 | IJMC | Indian oncology |

**Key guideline bodies:** NCCN (US), ASCO (US), ESMO (Europe)

### NEPHROLOGY (Kidney)
**Parent Society:** American Society of Nephrology (ASN) + Kidney Disease: Improving Global Outcomes (KDIGO) + International Society of Nephrology (ISN)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Journal of the American Society of Nephrology (JASN) | 10.3 | ASN | Flagship nephrology |
| Parent | Kidney International | 14.8 | ISN/Elsevier | International nephrology |
| Child | Clinical Journal of the American Society of Nephrology (CJASN) | 9.4 | ASN | Clinical nephrology |
| Child | Kidney Disease: Improving Global Outcomes (KDIGO) Guidelines | — | KDIGO | Clinical practice guidelines |
| Child | Nephrology Dialysis Transplantation | 5.2 | ERA | European nephrology |
| Child | American Journal of Kidney Diseases | 9.4 | NKF | Clinical kidney disease |
| Regional | Indian Journal of Nephrology | 1.0 | ISN India | Indian nephrology |

**Key guideline body:** KDIGO (global standard for kidney disease guidelines)

### NEUROLOGY (Brain & Nervous System)
**Parent Society:** American Academy of Neurology (AAN) + European Academy of Neurology (EAN)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Lancet Neurology | 46.4 | Elsevier | Highest-impact neurology |
| Parent | JAMA Neurology | 20.4 | AMA | Clinical neurology |
| Parent | Annals of Neurology | 11.2 | ANA | Clinical + basic neuroscience |
| Child | Neurology | 9.9 | AAN | AAN flagship — guidelines, clinical |
| Child | Brain | 10.6 | Oxford | European neuroscience, disease mechanisms |
| Child | Stroke | 7.9 | AHA | Cerebrovascular disease |
| Child | Epilepsia | 5.6 | ILAE | Epilepsy-specific |
| Child | Movement Disorders | 8.6 | MDS | Parkinson's, dystonia, tremor |
| Regional | Neurology India | 1.6 | Neurological Society of India | Indian neurology |

### PULMONOLOGY / RESPIRATORY (Lungs)
**Parent Society:** American Thoracic Society (ATS) + European Respiratory Society (ERS) + Global Initiative for Asthma (GINA)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | American Journal of Respiratory and Critical Care Medicine | 19.3 | ATS | Flagship respiratory + critical care |
| Parent | European Respiratory Journal | 16.6 | ERS | European respiratory medicine |
| Child | Thorax | 9.0 | BMJ/BTS | British thoracic medicine |
| Child | Chest | 9.6 | ACCP | Pulmonary, critical care, sleep |
| Child | Lancet Respiratory Medicine | 38.7 | Elsevier | High-impact respiratory |
| Regional | Indian Journal of Chest Diseases and Allied Sciences | 0.4 | — | Indian pulmonology |

### GASTROENTEROLOGY (GI / Liver)
**Parent Society:** American Gastroenterological Association (AGA) + American College of Gastroenterology (ACG) + European Association for the Study of the Liver (EASL)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Gastroenterology | 25.7 | AGA | Flagship GI journal |
| Parent | Gut | 23.0 | BMJ/BSG | British/European GI |
| Child | Hepatology | 12.9 | AASLD | Liver disease-specific |
| Child | American Journal of Gastroenterology | 9.8 | ACG | Clinical GI |
| Child | Journal of Hepatology | 25.7 | EASL | European liver disease |
| Child | Clinical Gastroenterology and Hepatology | 11.6 | AGA | Clinical practice |
| Child | Inflammatory Bowel Diseases | 4.5 | CCF | IBD-specific |
| Child | Diseases of the Colon and Rectum | 3.7 | ASCRS | Colorectal surgery/GI |
| Regional | Indian Journal of Gastroenterology | 2.0 | ISG | Indian GI |

### ENDOCRINOLOGY (Hormones / Diabetes / Thyroid)
**Parent Society:** American Diabetes Association (ADA) + Endocrine Society + European Association for the Study of Diabetes (EASD)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Diabetes Care | 14.8 | ADA | Diabetes clinical management — ADA Standards of Care |
| Parent | Lancet Diabetes & Endocrinology | 44.9 | Elsevier | Highest-impact endocrinology |
| Child | Diabetes | 7.7 | ADA | Diabetes research |
| Child | Diabetologia | 8.4 | EASD | European diabetes |
| Child | Journal of Clinical Endocrinology & Metabolism | 5.8 | Endocrine Society | Clinical endocrinology |
| Child | Thyroid | 5.3 | ATA | Thyroid disease |
| Regional | Indian Journal of Endocrinology and Metabolism | 1.2 | IJEM | Indian endocrinology |
| Regional | RSSDI (Research Society for Study of Diabetes in India) | — | RSSDI | Indian diabetes guidelines |

### INFECTIOUS DISEASE
**Parent Society:** Infectious Diseases Society of America (IDSA) + European Society of Clinical Microbiology and Infectious Diseases (ESCMID)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Clinical Infectious Diseases | 8.2 | IDSA | Flagship — IDSA/SHEA guidelines |
| Parent | Lancet Infectious Diseases | 36.4 | Elsevier | High-impact ID |
| Child | Journal of Infectious Diseases | 5.0 | IDSA | Basic + clinical ID |
| Child | Clinical Microbiology and Infection | 7.9 | ESCMID | European ID |
| Child | Journal of Antimicrobial Chemotherapy | 4.8 | BSAC | Antimicrobial resistance |
| Child | Emerging Infectious Diseases | 7.2 | CDC | Emerging pathogens |
| Child | JAMA Network Open (ID section) | 13.8 | AMA | Open-access ID research |
| Regional | Indian Journal of Medical Microbiology | 1.5 | IAMM | Indian microbiology |

### RHEUMATOLOGY (Joints / Autoimmune)
**Parent Society:** American College of Rheumatology (ACR) + European Alliance of Associations for Rheumatology (EULAR)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Annals of the Rheumatic Diseases | 20.3 | EULAR/BMJ | Flagship rheumatology |
| Parent | Arthritis & Rheumatology | 13.3 | ACR | ACR flagship |
| Child | Rheumatology | 4.7 | Oxford/BSR | British/clinical rheumatology |
| Child | Lupus | 1.5 | — | SLE-specific |
| Regional | Indian Journal of Rheumatology | 0.5 | IRA | Indian rheumatology |

### PSYCHIATRY / MENTAL HEALTH
**Parent Society:** American Psychiatric Association (APA) + World Psychiatric Association (WPA)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | American Journal of Psychiatry | 17.7 | APA | Flagship psychiatry |
| Parent | Lancet Psychiatry | 30.8 | Elsevier | High-impact psychiatry |
| Child | JAMA Psychiatry | 22.5 | AMA | Clinical psychiatry |
| Child | British Journal of Psychiatry | 8.7 | RCPsych | British psychiatry |
| Child | Biological Psychiatry | 9.6 | SOBP | Neuroscience of psychiatry |
| Child | World Psychiatry | 73.3 | WPA | Global psychiatry |
| Regional | Indian Journal of Psychiatry | 1.4 | IPS | Indian psychiatry |

### DERMATOLOGY (Skin)
**Parent Society:** American Academy of Dermatology (AAD) + European Academy of Dermatology and Venereology (EADV)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | JAMA Dermatology | 10.3 | AMA | Clinical dermatology |
| Parent | British Journal of Dermatology | 11.0 | BAD | British/European dermatology |
| Child | Journal of the American Academy of Dermatology | 11.5 | AAD | AAD flagship |
| Child | Journal of Investigative Dermatology | 6.5 | SID | Research dermatology |
| Regional | Indian Dermatology Online Journal | 1.0 | IADVL | Indian dermatology |
| Regional | Indian Journal of Dermatology | 0.7 | — | Indian skin disease |

### OPHTHALMOLOGY (Eyes)
**Parent Society:** American Academy of Ophthalmology (AAO)

| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Ophthalmology | 13.7 | AAO | Flagship ophthalmology |
| Child | JAMA Ophthalmology | 7.6 | AMA | Clinical ophthalmology |
| Child | British Journal of Ophthalmology | 4.1 | BMJ | British/European |
| Child | American Journal of Ophthalmology | 4.1 | — | US clinical |
| Regional | Indian Journal of Ophthalmology | 2.0 | AIOS | Indian ophthalmology |

### ORTHOPEDICS / SURGERY (Bones & Joints)
| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Journal of Bone and Joint Surgery (JBJS) | 5.3 | — | US flagship orthopedics |
| Parent | Bone & Joint Journal | 4.9 | BOA | British orthopedics |
| Child | Clinical Orthopaedics and Related Research | 4.2 | AAOS | Clinical orthopedics |
| Child | Arthroscopy | 4.4 | AANA | Sports surgery |

### RADIOLOGY (Imaging)
| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Radiology | 15.2 | RSNA | Flagship imaging |
| Child | American Journal of Roentgenology | 4.7 | ARRS | Clinical radiology |
| Child | European Radiology | 4.9 | ESR | European imaging |

### OBSTETRICS & GYNECOLOGY (Women's Health / Pregnancy)
| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | American Journal of Obstetrics and Gynecology | 9.8 | — | Flagship OB/GYN |
| Parent | BJOG | 6.4 | RCOG | British OB/GYN |
| Child | Obstetrics & Gynecology ("The Green Journal") | 7.2 | ACOG | ACOG flagship |
| Child | Fertility and Sterility | 6.6 | ASRM | Reproductive medicine |
| Regional | Journal of Obstetrics and Gynaecology of India | 0.7 | FOGSI | Indian OB/GYN |

### PEDIATRICS (Children)
| Tier | Journal | IF | Society | Focus |
|------|---------|-----|---------|-------|
| Parent | Pediatrics | 8.0 | AAP | AAP flagship — child health |
| Parent | JAMA Pediatrics | 26.1 | AMA | High-impact pediatrics |
| Child | Journal of Pediatrics | 3.7 | — | Clinical pediatrics |
| Child | Archives of Disease in Childhood | 3.2 | BMJ/RCPCH | British pediatrics |
| Child | Lancet Child & Adolescent Health | 19.6 | Elsevier | High-impact child health |
| Regional | Indian Pediatrics | 1.8 | IAP | Indian pediatrics |
| Regional | Indian Journal of Pediatrics | 1.4 | — | Indian child health |

### NON-US / NON-EUROPEAN HIGH-REPUTATION JOURNALS

| Journal | Country | IF | Specialty | Notes |
|---------|---------|-----|-----------|-------|
| Canadian Medical Association Journal (CMAJ) | Canada | 8.4 | General | Canadian flagship |
| Medical Journal of Australia (MJA) | Australia | 5.4 | General | Australian flagship |
| Chinese Medical Journal | China | 6.1 | General | Chinese Medical Association |
| Japan Medical Association Journal (JMAJ) | Japan | 1.4 | General | Japanese flagship |
| Korean Journal of Internal Medicine | South Korea | 2.4 | Internal Med | Korean flagship |
| Annals of the Academy of Medicine, Singapore | Singapore | 1.8 | General | SE Asian flagship |
| Saudi Medical Journal | Saudi Arabia | 1.3 | General | Middle East reference |
| African Journal of Emergency Medicine | South Africa | 1.7 | Emergency | African EM |
| National Medical Journal of India | India | 1.5 | General | Indian general medicine |
| Journal of the Association of Physicians of India (JAPI) | India | 0.6 | Internal Med | Widely read by Indian physicians |

---

# PART 3: Complete Medical Specialties & Subspecialties

*Based on ABMS (American Board of Medical Specialties) 40 primary specialties and 89+ subspecialties, adapted for Hunt AI's system prompt engineering.*

## 3.1 Primary Care Specialties

### Family Medicine
**What they do:** Provide comprehensive primary care to patients of ALL ages — newborns through elderly. They manage chronic diseases (diabetes, hypertension), perform preventive care (screenings, vaccinations), and handle acute illnesses. The "front door" of medicine.
**System prompt note:** Queries from family medicine doctors are often broad, multi-system. They need practical, actionable answers, not deep subspecialty detail.
**Key journals:** Annals of Family Medicine, Journal of Family Practice, American Family Physician
**Subspecialties:** Adolescent Medicine, Geriatric Medicine, Hospice/Palliative Medicine, Sports Medicine

### Internal Medicine
**What they do:** Diagnose and treat complex adult diseases across ALL organ systems. They are the "doctor's doctor" — generalists who handle the most diagnostically challenging cases. Many subspecialize (see below).
**System prompt note:** Internists ask the most complex queries. They expect evidence-based answers with GRADE levels and guideline citations.
**Key journals:** Annals of Internal Medicine, JAMA Internal Medicine
**Subspecialties:** Cardiology, Gastroenterology, Pulmonology, Nephrology, Endocrinology, Hematology, Infectious Disease, Rheumatology, Oncology, Geriatric Medicine, Critical Care Medicine, Allergy & Immunology

### Pediatrics
**What they do:** Medical and surgical care for infants, children, and adolescents (birth to 18-21 years). They account for developmental stages, weight-based dosing, age-specific diseases, and vaccine schedules.
**System prompt note:** ALWAYS flag weight-based dosing. Drug safety profiles differ dramatically in children vs adults. Many adult drugs are contraindicated or require different dosing in pediatrics.
**Key journals:** Pediatrics (AAP), JAMA Pediatrics, Journal of Pediatrics
**Subspecialties:** Pediatric Cardiology, Pediatric Gastroenterology, Pediatric Pulmonology, Pediatric Nephrology, Pediatric Neurology, Pediatric Endocrinology, Pediatric Hematology-Oncology, Pediatric Infectious Disease, Pediatric Rheumatology, Pediatric Critical Care, Neonatology, Pediatric Surgery, Pediatric Emergency Medicine, Developmental-Behavioral Pediatrics, Adolescent Medicine

### Emergency Medicine
**What they do:** Immediate assessment and treatment of acute injuries and illnesses in the emergency department. They handle everything from chest pain to trauma to stroke codes. Speed and triage are paramount.
**System prompt note:** Emergency queries need IMMEDIATE, protocol-driven answers. ACLS, ATLS, toxicology dosing. Always include "call 108/102" for life-threatening conditions.
**Key journals:** Annals of Emergency Medicine, Academic Emergency Medicine, Emergency Medicine Journal
**Subspecialties:** Pediatric Emergency Medicine, Medical Toxicology, Sports Medicine, Emergency Medical Services, Critical Care (EM pathway)

## 3.2 Medical Subspecialties (Internal Medicine Children)

### Cardiology
**Focus:** Heart disease — coronary artery disease, heart failure, arrhythmias, valvular disease, hypertension, cardiomyopathy, congenital heart disease.
**Sub-subspecialties:** Interventional Cardiology (angioplasty, stents), Electrophysiology (arrhythmia ablation, pacemakers/ICDs), Heart Failure & Transplant, Cardiac Imaging (echo, CT, MRI), Preventive Cardiology
**Route to:** Circulation, JACC, European Heart Journal

### Gastroenterology
**Focus:** GI tract (esophagus, stomach, intestines, colon), liver (hepatology), pancreas, gallbladder. Conditions include IBD, IBS, GERD, cirrhosis, hepatitis, pancreatitis, GI cancers, celiac disease.
**Sub-subspecialties:** Hepatology, Advanced Endoscopy (ERCP, EUS), Inflammatory Bowel Disease, Motility Disorders, Transplant Hepatology
**Route to:** Gastroenterology, Gut, Hepatology

### Pulmonology / Respiratory Medicine
**Focus:** Lung and airway diseases — asthma, COPD, pneumonia, pulmonary fibrosis, lung cancer, pulmonary hypertension, sleep apnea, sarcoidosis.
**Sub-subspecialties:** Critical Care Medicine (ICU), Interventional Pulmonology, Sleep Medicine
**Route to:** AJRCCM, European Respiratory Journal, Chest

### Nephrology
**Focus:** Kidney diseases — CKD, acute kidney injury, dialysis, transplant, glomerulonephritis, electrolyte disorders, hypertension (renal causes), polycystic kidney disease.
**Route to:** JASN, Kidney International, AJKD, KDIGO Guidelines

### Endocrinology
**Focus:** Hormonal disorders — diabetes (Type 1, Type 2, gestational), thyroid disease, adrenal disorders, pituitary tumors, osteoporosis, PCOS, hypogonadism, metabolic bone disease.
**Route to:** Diabetes Care, JCEM, Lancet Diabetes & Endocrinology

### Hematology
**Focus:** Blood disorders — anemia, clotting disorders (DVT/PE), bleeding disorders (hemophilia), blood cancers (leukemia, lymphoma, myeloma), sickle cell disease, thalassemia.
**Route to:** Blood, Journal of Clinical Oncology (heme-onc), Haematologica

### Medical Oncology
**Focus:** Cancer treatment using systemic therapies — chemotherapy, targeted therapy, immunotherapy, hormone therapy. Manages solid tumors and hematologic malignancies.
**Route to:** JCO, Lancet Oncology, Annals of Oncology, JAMA Oncology

### Infectious Disease
**Focus:** Bacterial, viral, fungal, and parasitic infections. HIV/AIDS, tuberculosis, hepatitis, antimicrobial resistance, hospital-acquired infections, travel medicine, tropical diseases.
**Route to:** Clinical Infectious Diseases, Lancet Infectious Diseases, Journal of Antimicrobial Chemotherapy

### Rheumatology
**Focus:** Autoimmune and musculoskeletal diseases — rheumatoid arthritis, systemic lupus erythematosus (SLE), gout, ankylosing spondylitis, vasculitis, scleroderma, Sjögren syndrome.
**Route to:** Annals of the Rheumatic Diseases, Arthritis & Rheumatology

### Allergy & Immunology
**Focus:** Allergic diseases (asthma, rhinitis, drug allergies, food allergies, anaphylaxis), immune deficiency disorders, autoimmune conditions.
**Route to:** Journal of Allergy and Clinical Immunology, Allergy (EAACI)

### Critical Care / Intensive Care Medicine
**Focus:** Life-threatening conditions requiring ICU care — sepsis, ARDS, shock, multi-organ failure, mechanical ventilation, hemodynamic monitoring.
**Route to:** Critical Care Medicine, Intensive Care Medicine, CHEST

### Geriatric Medicine
**Focus:** Health care of elderly patients (65+) — polypharmacy, falls, cognitive decline, frailty, end-of-life care, delirium, functional assessment.
**Route to:** Journal of the American Geriatrics Society, Age and Ageing

## 3.3 Surgical Specialties

### General Surgery
**Focus:** Abdominal operations — appendectomy, cholecystectomy, hernia repair, bowel resection, thyroidectomy, breast surgery. Many general surgeons subspecialize further.
**Subspecialties:** Surgical Critical Care, Trauma Surgery, Surgical Oncology, Minimally Invasive Surgery, Bariatric Surgery

### Neurosurgery
**Focus:** Brain and spinal cord surgery — brain tumors, aneurysms, spinal disc herniation, spinal cord injuries, hydrocephalus, epilepsy surgery, deep brain stimulation.
**Route to:** Journal of Neurosurgery, Neurosurgery

### Orthopedic Surgery
**Focus:** Musculoskeletal system — fractures, joint replacement, ACL repair, spinal surgery, sports injuries, bone tumors, pediatric orthopedics.
**Subspecialties:** Sports Medicine, Hand Surgery, Spine Surgery, Joint Replacement, Pediatric Orthopedics, Trauma, Oncology
**Route to:** JBJS, Clinical Orthopaedics

### Cardiothoracic Surgery
**Focus:** Heart and chest surgery — coronary artery bypass grafting (CABG), valve repair/replacement, aortic aneurysm repair, lung cancer resection, esophageal surgery, heart transplant.
**Route to:** Journal of Thoracic and Cardiovascular Surgery, Annals of Thoracic Surgery

### Vascular Surgery
**Focus:** Blood vessel surgery — carotid endarterectomy, aortic aneurysm repair, peripheral artery bypass, endovascular stenting, dialysis access creation.

### Urology
**Focus:** Urinary tract and male reproductive system — kidney stones, prostate cancer, BPH, bladder cancer, incontinence, erectile dysfunction, infertility.
**Route to:** Journal of Urology, European Urology

### Plastic Surgery
**Focus:** Reconstructive and cosmetic surgery — burn reconstruction, hand surgery, microsurgery, craniofacial surgery, breast reconstruction, cosmetic procedures.

### Otolaryngology (ENT — Ear, Nose, Throat)
**Focus:** Diseases of the ear, nose, throat, head, and neck — hearing loss, sinusitis, tonsillitis, head and neck cancers, voice disorders, sleep apnea surgery.

### Colon & Rectal Surgery
**Focus:** Surgical diseases of the colon, rectum, and anus — colorectal cancer, IBD requiring surgery, hemorrhoids, rectal prolapse, fistulas.

## 3.4 Diagnostic & Support Specialties

### Radiology
**Focus:** Medical imaging — X-ray, CT, MRI, ultrasound, PET, mammography. Interventional radiologists perform minimally invasive image-guided procedures.
**Subspecialties:** Diagnostic Radiology, Interventional Radiology, Neuroradiology, Musculoskeletal Radiology, Breast Imaging, Pediatric Radiology, Nuclear Medicine

### Pathology
**Focus:** Diagnosing disease through laboratory analysis of body tissues, fluids, and cells. Surgical pathology (biopsies), cytopathology (Pap smears), clinical pathology (blood tests), forensic pathology.
**Subspecialties:** Anatomic Pathology, Clinical Pathology, Dermatopathology, Hematopathology, Neuropathology, Forensic Pathology, Molecular Genetic Pathology

### Anesthesiology
**Focus:** Perioperative care — administering anesthesia for surgery, pain management, critical care, airway management, regional anesthesia.
**Subspecialties:** Critical Care Medicine, Pain Medicine, Cardiac Anesthesia, Neuroanesthesia, Pediatric Anesthesia, Obstetric Anesthesia

### Physical Medicine & Rehabilitation (PM&R / Physiatry)
**Focus:** Restoring function after injury or illness — stroke rehabilitation, spinal cord injury, traumatic brain injury, musculoskeletal pain, sports medicine, amputee care.

## 3.5 Other Specialties

### Psychiatry
**Focus:** Mental health — depression, anxiety, bipolar disorder, schizophrenia, PTSD, substance abuse, eating disorders, OCD, ADHD.
**Subspecialties:** Child & Adolescent Psychiatry, Geriatric Psychiatry, Addiction Psychiatry, Forensic Psychiatry, Consultation-Liaison Psychiatry, Neuropsychiatry

### Dermatology
**Focus:** Skin, hair, and nail diseases — eczema, psoriasis, acne, skin cancer (melanoma, basal cell, squamous cell), autoimmune skin diseases, infections.
**Subspecialties:** Dermatopathology, Pediatric Dermatology, Mohs Surgery (skin cancer surgery)

### Ophthalmology
**Focus:** Eye diseases and surgery — cataracts, glaucoma, macular degeneration, diabetic retinopathy, retinal detachment, refractive surgery (LASIK).

### Obstetrics & Gynecology
**Focus:** Women's reproductive health — pregnancy/delivery, contraception, infertility, menstrual disorders, cervical/ovarian/uterine cancers, menopause, PCOS.
**Subspecialties:** Maternal-Fetal Medicine (high-risk pregnancy), Reproductive Endocrinology & Infertility, Gynecologic Oncology, Female Pelvic Medicine & Reconstructive Surgery

### Preventive Medicine / Public Health
**Focus:** Disease prevention at the population level — epidemiology, occupational health, environmental medicine, health policy, vaccination programs, chronic disease prevention.

### Nuclear Medicine
**Focus:** Using radioactive materials for diagnosis (PET, SPECT scanning) and treatment (radioactive iodine for thyroid cancer, radioimmunotherapy).

### Medical Genetics & Genomics
**Focus:** Genetic disorders — chromosomal abnormalities, inborn errors of metabolism, hereditary cancer syndromes, genetic counseling, prenatal genetic testing.

---

# PART 4: Demographic Differences in Medicine

## 4.1 Sex-Based Differences

### Why This Matters for Hunt AI
The same disease often presents differently in males vs females. Drug metabolism differs. Risk profiles differ. When a doctor asks about "heart attack symptoms," the answer should note sex-specific presentations.

### Cardiovascular
| Factor | Male | Female |
|--------|------|--------|
| Presentation of MI | Classic: crushing chest pain, left arm radiation | Often atypical: jaw pain, nausea, fatigue, back pain, shortness of breath |
| Risk timing | Higher risk starting age 45 | Risk increases significantly post-menopause (age 55+) |
| Coronary artery disease | More epicardial (large vessel) disease | More microvascular disease, coronary vasospasm |
| Medication response | Standard statin dosing | Women may have more statin-related myalgia |
| Heart failure | More HFrEF (reduced ejection fraction) | More HFpEF (preserved ejection fraction) |

### Metabolic / Endocrine
| Factor | Male | Female |
|--------|------|--------|
| Diabetes risk | Higher at lower BMI | PCOS increases insulin resistance risk |
| Thyroid disease | Less common | 5-8x more common (especially Hashimoto's, Graves') |
| Osteoporosis | Less common, later onset | Very common post-menopause (estrogen decline) |
| Gout | Much more common | Rare before menopause (estrogen is uricosuric) |

### Drug Metabolism
| Factor | Male | Female |
|--------|------|--------|
| Body composition | Higher muscle mass, lower fat percentage | Higher fat percentage — affects distribution of lipophilic drugs |
| Kidney function | Higher baseline eGFR | Lower baseline eGFR — dose adjustments needed earlier |
| CYP enzyme activity | CYP1A2 more active | CYP3A4 more active — affects metabolism of many drugs |
| Drug dosing | Standard dosing often validated primarily in male subjects | Many drugs need dose adjustment (e.g., zolpidem: FDA reduced female dose by 50%) |

### Autoimmune Disease
Females are disproportionately affected by autoimmune diseases:
- Systemic lupus erythematosus (SLE): 9:1 female to male ratio
- Rheumatoid arthritis: 3:1 female to male
- Multiple sclerosis: 3:1 female to male
- Hashimoto's thyroiditis: 10:1 female to male
- Sjögren syndrome: 9:1 female to male

### Reproductive-Specific Conditions
| Male-Specific | Female-Specific |
|---|---|
| Prostate cancer, BPH | Cervical, ovarian, endometrial cancer |
| Testicular cancer | Breast cancer (also occurs in males, rarely) |
| Erectile dysfunction | PCOS, endometriosis |
| Male pattern baldness | Pregnancy-related conditions (preeclampsia, gestational diabetes) |
| Hypogonadism | Menopause and related complications |

## 4.2 Age-Based Differences

### Pediatric Considerations (Birth to 18 years)
- ALL drug dosing is weight-based (mg/kg) or body surface area-based
- Organ systems are still developing — liver and kidney function differ from adults
- Many drugs are NOT approved for pediatric use (off-label prescribing is common)
- Developmental milestones affect disease presentation and treatment compliance
- Vaccine schedules are age-specific (IAP schedule in India differs from CDC schedule)
- Fever management thresholds differ (neonates vs children vs adolescents)

### Geriatric Considerations (65+ years)
- Polypharmacy is the norm — average elderly patient takes 5-9 medications
- Renal function declines with age — CrCl/eGFR-based dose adjustments are CRITICAL
- Increased fall risk — certain medications (benzodiazepines, anticholinergics) are on the Beers Criteria list of potentially inappropriate medications
- Frailty assessment affects treatment aggressiveness
- Hepatic metabolism slows — longer drug half-lives
- Cognitive screening (dementia, delirium) affects medication adherence
- Goals of care shift toward quality of life over aggressive treatment
- Beers Criteria (AGS) — list of medications to avoid in elderly patients

---

# PART 5: Hunt AI Retrieval Routing Map

## 5.1 Specialty → Journal Routing (for Query Router)

```python
# When query router detects specialty, prioritize these journal ISSNs in PubMed search
SPECIALTY_JOURNAL_PRIORITY = {
    "cardiology": [
        "0009-7322",  # Circulation
        "0735-1097",  # JACC
        "0195-668X",  # European Heart Journal
    ],
    "oncology": [
        "0732-183X",  # JCO
        "1470-2045",  # Lancet Oncology
        "0923-7534",  # Annals of Oncology
    ],
    "nephrology": [
        "1046-6673",  # JASN
        "0085-2538",  # Kidney International
    ],
    "gastroenterology": [
        "0016-5085",  # Gastroenterology
        "0017-5749",  # Gut
        "0270-9139",  # Hepatology
    ],
    "infectious_disease": [
        "1058-4838",  # Clinical Infectious Diseases
        "1473-3099",  # Lancet Infectious Diseases
    ],
    "endocrinology": [
        "0149-5992",  # Diabetes Care
        "0021-972X",  # JCEM
    ],
    "pulmonology": [
        "1073-449X",  # AJRCCM
        "0903-1936",  # European Respiratory Journal
    ],
    "neurology": [
        "1474-4422",  # Lancet Neurology
        "0028-3878",  # Neurology (AAN)
    ],
    "rheumatology": [
        "0003-4967",  # Annals of Rheumatic Diseases
        "2326-5191",  # Arthritis & Rheumatology
    ],
    "psychiatry": [
        "0002-953X",  # Am J Psychiatry
        "2215-0366",  # Lancet Psychiatry
    ],
    "pediatrics": [
        "0031-4005",  # Pediatrics (AAP)
        "2168-6211",  # JAMA Pediatrics
    ],
}
```

## 5.2 Evidence Hierarchy for Re-ranking

When multiple search results return, re-rank using this hierarchy:

1. **Society practice guidelines** from the governing body for that specialty (e.g., ACC/AHA for cardiology)
2. **Systematic reviews / meta-analyses** from Cochrane or published in the specialty's parent journal
3. **Phase 3 randomized controlled trials** published in Big 4 general journals or the specialty parent journal
4. **Large cohort / real-world evidence studies** published in specialty journals
5. **Expert reviews** in specialty journals (useful for context, not for specific claims)
6. **Case reports / case series** (lowest evidence, but valuable for rare conditions)
7. **Indian-specific guidelines** (ICMR STWs, CSI, RSSDI, ISN India) — elevated to Tier 1 when the user is specifically asking about Indian practice

## 5.3 PubMed Search Template for Hunt AI

```python
def build_pubmed_query(
    topic: str,
    specialty: str,
    study_type: str = None,  # "guideline", "rct", "meta-analysis", "review"
    years: tuple = (2023, 2026),
    humans_only: bool = True,
    age_group: str = None,  # "child", "adult", "aged"
    sex: str = None,  # "male", "female"
) -> str:
    """Build an optimized PubMed query for Hunt AI."""
    
    parts = [f'({topic})']
    
    # Add specialty MeSH if available
    if specialty in SPECIALTY_MESH_MAP:
        parts.append(SPECIALTY_MESH_MAP[specialty])
    
    # Species filter
    if humans_only:
        parts.append('Humans[MeSH]')
    
    # Study type
    type_map = {
        "guideline": 'Practice Guideline[pt]',
        "rct": 'Randomized Controlled Trial[pt]',
        "meta_analysis": 'Meta-Analysis[pt]',
        "systematic_review": 'systematic[sb]',
        "clinical_trial": 'Clinical Trial[pt]',
    }
    if study_type and study_type in type_map:
        parts.append(type_map[study_type])
    
    # Date range
    if years:
        parts.append(f'("{years[0]}"[PDAT] : "{years[1]}"[PDAT])')
    
    # Demographics
    if age_group:
        age_mesh = {
            "newborn": '"Infant, Newborn"[MeSH]',
            "infant": '"Infant"[MeSH]',
            "child": '"Child"[MeSH]',
            "adolescent": '"Adolescent"[MeSH]',
            "adult": '"Adult"[MeSH]',
            "middle_aged": '"Middle Aged"[MeSH]',
            "aged": '"Aged"[MeSH]',
            "elderly": '"Aged, 80 and over"[MeSH]',
        }
        if age_group in age_mesh:
            parts.append(age_mesh[age_group])
    
    if sex:
        parts.append(f'{sex.capitalize()}[MeSH]')
    
    return ' AND '.join(parts)
```

---

# PART 6: Key Guideline Bodies for Each Specialty

These are the organizations whose guidelines should be treated as HIGHEST AUTHORITY in Hunt AI's source hierarchy:

| Specialty | Guideline Body | Country | Website |
|---|---|---|---|
| General | WHO | International | who.int |
| Cardiology | ACC/AHA | USA | acc.org, heart.org |
| Cardiology | ESC | Europe | escardio.org |
| Cardiology | CSI | India | csi.org.in |
| Oncology | NCCN | USA | nccn.org |
| Oncology | ASCO | USA | asco.org |
| Oncology | ESMO | Europe | esmo.org |
| Nephrology | KDIGO | International | kdigo.org |
| Diabetes | ADA | USA | diabetes.org |
| Diabetes | EASD | Europe | easd.org |
| Diabetes | RSSDI | India | rssdi.in |
| Infectious Disease | IDSA | USA | idsociety.org |
| Infectious Disease | ESCMID | Europe | escmid.org |
| Pulmonology | ATS/ERS | USA/Europe | thoracic.org |
| Asthma | GINA | International | ginasthma.org |
| COPD | GOLD | International | goldcopd.org |
| Rheumatology | ACR/EULAR | USA/Europe | rheumatology.org |
| Gastroenterology | AGA/ACG | USA | gastro.org |
| Liver | AASLD/EASL | USA/Europe | aasld.org |
| Psychiatry | APA | USA | psychiatry.org |
| Pediatrics | AAP | USA | aap.org |
| Pediatrics | IAP | India | iapindia.org |
| OB/GYN | ACOG | USA | acog.org |
| Stroke | AHA/ASA | USA | stroke.org |
| Allergy | AAAAI/EAACI | USA/Europe | aaaai.org |
| India (all) | ICMR | India | icmr.gov.in |
| India (all) | NMC | India | nmc.org.in |
| India (drugs) | CDSCO | India | cdsco.gov.in |
| Systematic Reviews | Cochrane | International | cochranelibrary.com |

---

*This document should be loaded into the system prompt context or used as the routing table for Hunt AI's query understanding module. When a doctor asks a cardiology question, retrieve from Circulation/JACC/EHJ first. When they ask about diabetes, go to Diabetes Care and ADA Standards. This is how OpenEvidence achieves specialty-appropriate citations — and this is how Hunt AI will match that quality.*
