# Always-On Rules — Noocyte AI

These rules apply to **every response, every query, every component, every time**. They are not suggestions. They are not defaults. They are invariants — conditions that must hold true in every single output the system produces.

Any code, prompt, or agent that violates these rules must be corrected before it can be merged or deployed.

---

## Rule 1: No Prescriptive Language

**The rule:** Noocyte AI never tells a doctor what to prescribe, administer, or give a patient.

**Prohibited phrases (exact strings — search for these in every output):**
- "prescribe"
- "administer"
- "give the patient"
- "give your patient"
- "start the patient on"
- "start on"
- "you should give"
- "I recommend giving"
- "the patient should receive" (when used as a direct instruction)

**Required replacements:**
- "Guidelines recommend [N]"
- "Evidence supports [N]"
- "According to [source] [N], the standard approach is..."
- "The [guideline body] [year] recommends [N]..."

**Why this rule exists:** Noocyte AI is a decision support tool, not a prescribing system. The doctor makes the clinical decision. Noocyte AI provides the evidence. This distinction is both a legal requirement and an ethical obligation.

---

## Rule 2: Every Factual Claim Must Be Cited

**The rule:** Every statement of medical fact — every percentage, every hazard ratio, every p-value, every NNT, every guideline recommendation — must have an inline `[N]` citation that maps to a specific entry in the `citations` array.

**Prohibited patterns:**
- "Studies show that..." (no citation)
- "Research suggests..." (no citation)
- "It is well established that..." (no citation)
- "The evidence indicates..." (no citation)
- Any statistical figure without `[N]`

**Required pattern:**
- "Fidaxomicin reduces recurrence by 36% compared to vancomycin (16% vs 25%) [1]"
- "The ARISTOTLE trial demonstrated a 21% relative risk reduction in stroke [2]"

**Citation integrity rules:**
- Citations are 1-indexed and sequential: [1], [2], [3]...
- Every [N] in the answer body must have a matching entry in `citations[N-1]`
- Every entry in `citations` must be referenced in the answer body
- No citation numbers may be skipped

---

## Rule 3: Acute/Emergency Clinical Protocol Priority

**The rule:** When an emergency or acute clinical scenario is detected (e.g., stroke, MI, anaphylaxis), the system must prioritize **immediate, evidence-based management protocols**. The answer must focus on the "Golden Hour" interventions that the doctor needs to perform.

**Clinical Focus Areas:**
- Stroke: Thrombolysis/Thrombectomy windows and eligibility [N]
- MI: Loading doses (DAPT), STEMI vs NSTEMI protocols [N]
- Anaphylaxis: Adrenaline dosing and airway management [N]
- Sepsis: Hour-1 bundle, fluid resuscitation, and empiric antibiotics [N]

**Required Response Structure for Acute Cases:**
1. **IMMEDIATE ACTION:** The very first sentence (BLUF) must state the first-line intervention.
2. **TIMING:** Explicitly mention time-sensitive windows (e.g., "within 4.5 hours").
3. **DOSE/PROTOCOL:** Provide specific, cited protocols from ICMR or international guidelines.

**Why:** This tool is for doctors. They do not need to be told to call an ambulance; they need the evidence-based protocol to treat the patient in front of them immediately.

---

## Rule 4: PII Must Be Redacted Before Logging or External API Calls

**The rule:** No personally identifiable information (PII) may appear in any log file, analytics database, cache key, or external API call.

**PII that must be redacted:**
- Aadhaar numbers (12-digit, any format)
- Indian mobile phone numbers (+91 or 10-digit starting with 6-9)
- PAN card numbers (5 letters + 4 digits + 1 letter)
- Patient names (any text matching "patient Mr./Mrs./Dr. [Name]" pattern)
- Email addresses

**The `redact_pii()` function must be called:**
1. Before any `logger.info()`, `logger.debug()`, or `logger.warning()` that includes query text
2. Before any query text is sent to Gemini, Cohere, or Tavily
3. Before any query text is used as a Redis cache key
4. Before any query text is written to BigQuery

---

## Rule 5: Temperature Must Be ≤ 0.1 for All Medical Generation

**The rule:** Every Gemini API call that generates medical content must use `temperature=0.0`. The maximum permitted temperature for any medical generation is `0.1`.

**Why:** Medical answers must be deterministic and reproducible. A doctor who asks the same question twice must receive the same answer. High temperature introduces randomness that can cause factual inconsistencies.

**The only exception:** Creative tasks (e.g., generating a WhatsApp welcome message) may use temperature up to 0.7. These are not medical generation tasks.

---

## Rule 6: ICMR Guidelines Take Priority for Indian Conditions

**The rule:** For any condition that has an ICMR Standard Treatment Workflow or ICMR guideline, that document must appear as the first citation in the response, before any international guideline.

**Conditions with known ICMR guidelines (non-exhaustive):**
- Tuberculosis (all forms)
- Malaria
- Dengue fever
- Typhoid fever
- Kala-azar (visceral leishmaniasis)
- COVID-19
- Type 2 diabetes (RSSDI + ICMR joint guidelines)
- Hypertension
- Anaemia
- Vitamin D deficiency

**If no ICMR guideline exists for the condition:** Use the international guideline hierarchy (ACC/AHA > ESC > IDSA > ADA > KDIGO > NCCN > ASCO).

---

## Rule 7: Structured JSON Output is Always Enforced

**The rule:** Every Gemini call that produces a medical response must use:
- `response_mime_type="application/json"`
- A `response_schema` that enforces the `MedicalResponseSchema`
- `temperature=0.0`

Plain text responses from Gemini are never acceptable for medical content generation.

---

## Rule 8: Absolute Brand Neutrality

**The rule:** Noocyte AI is a transparent clinical search engine, not a brand promoter. Brand names (e.g., Dolo, Augmentin, Telma) must NEVER appear in the final output `answer` field.

**Required behavior:**
1. **Internal Resolution:** Resolve brand names to their International Nonproprietary Name (INN) internally before retrieval and generation.
2. **Generic-Only Output:** Use only the INN (generic name) in the final response to the doctor.
3. **Transparency:** If a brand name is used in the query, the answer should address the active ingredient directly without mentioning the brand.

**Why:** To maintain professional trust and transparency. We provide evidence for molecules and protocols, not marketing for pharmaceutical brands.

---

## Enforcement

These rules are enforced at three levels:

1. **Code review:** The `medical-code-reviewer` agent checks every PR for violations of these rules.
2. **Automated tests:** `tests/rules/test_always_on.py` runs these rules against the last 50 test queries on every CI build.
3. **Benchmark:** The `eval-benchmark` skill scores every response for Rule 1 (no prescriptive language) and Rule 2 (citation quality) as part of the standard benchmark run.

Any violation of Rules 1, 3, or 4 is a **CRITICAL** finding that blocks deployment.
Any violation of Rules 2, 5, 6, or 7 is a **WARNING** that must be fixed before the next sprint gate.
