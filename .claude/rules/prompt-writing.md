# Prompt Writing Rules — Noocyte AI

These rules govern every prompt written for Noocyte AI. They exist to prevent the most common and most damaging mistake in AI product development: writing prompts without a framework.

---

## Rule P-1: Read the Skill Before Writing Any Prompt

**The rule:** Before writing, editing, or reviewing any prompt for Noocyte AI, you MUST read `.claude/skills/system-prompter/SKILL.md`.

This applies to:
- The main system prompt
- The generation prompt passed to Gemini
- The reranking instruction
- The PICO extraction prompt
- The intent classification prompt
- The WhatsApp formatter instruction
- Any prompt template in any file

**There are no exceptions.** A prompt written without reading the skill will be rewritten.

---

## Rule P-2: Four Layers, Always

**The rule:** Every system prompt must follow the four-layer architecture:

1. `<identity>` — Who the system is and is not (≤ 5 sentences)
2. `<constraints>` — Hard ALWAYS/NEVER rules (≤ 6 rules)
3. `<routing>` — Conditional `<if_block>` logic for each query type
4. `<output_schema>` — Concrete JSON schema

Prompts that do not follow this structure are rejected.

---

## Rule P-3: The 800-Token Budget

**The rule:** No system prompt may exceed 800 tokens. If a prompt exceeds this limit, it must be cut before it is used.

**How to cut a prompt:**
1. Remove any instruction that duplicates another instruction
2. Remove any instruction that uses soft language ("try to", "prefer to") — replace with ALWAYS/NEVER or remove
3. Move query-type-specific instructions into `<if_block>` sections so they are only read when needed
4. Remove any background context that the model already knows (e.g., "Gemini is a large language model...")

---

## Rule P-4: No Soft Language

**The rule:** Prompts must use ALWAYS/NEVER language for all constraints. Soft language is prohibited.

| Prohibited | Required replacement |
|-----------|---------------------|
| "Try to cite sources" | "ALWAYS cite every factual claim with [N]" |
| "Prefer ICMR guidelines" | "ALWAYS cite ICMR first for Indian conditions" |
| "Avoid prescriptive language" | "NEVER use prescriptive language" |
| "It would be good to include..." | "ALWAYS include..." |
| "If possible, format as JSON" | "ALWAYS respond in the JSON schema below" |

---

## Rule P-5: The Emergency Block is Always First

**The rule:** In every prompt that includes routing logic, the emergency detection `<if_block>` must be the first block. No other block may precede it.

**Why:** Emergency detection must fire before any retrieval or generation. If the emergency block is buried in the middle of the routing section, there is a risk that a different block fires first.

---

## Rule P-6: Every Non-Emergency Block Must Include a Follow-Up Question

**The rule:** Every `<if_block>` that is not the emergency block must include an instruction to generate a `follow_up_question`. The follow-up question must be specific, clinically relevant, and answerable by Noocyte AI.

**Why:** The `follow_up_question` is the product's primary engagement mechanism. It is what keeps doctors using the tool, asking more questions, and spending more time with it. Omitting it is a product failure, not just a prompt failure.

---

## Rule P-7: Test Every Prompt Against All 10 Benchmark Queries

**The rule:** Before any prompt change is considered complete, it must be tested against all 10 OpenEvidence benchmark queries. The benchmark score must not decrease.

**How to run the test:**
```bash
python3 scripts/run_benchmark.py --queries tests/benchmark/openevidence_10.json
```

If the score decreases after a prompt change, the change must be reverted or corrected before it can be used.

---

## Rule P-8: Document Every Prompt Change

**The rule:** Every prompt change must be documented with:
- The reason for the change
- The token count before and after
- The benchmark score before and after
- The previous version (stored in `prompts/archive/`)

This documentation is maintained by the `system-prompter` agent.

---

## The Prompt Review Workflow

```
Developer wants to change a prompt
        ↓
Read skills/system-prompter/SKILL.md
        ↓
Draft the change following the four-layer architecture
        ↓
Run the Prompt Audit Checklist (from the skill)
        ↓
Count tokens — must be ≤ 800
        ↓
Test against all 10 benchmark queries
        ↓
Score ≥ previous score?
  YES → Submit for review by system-prompter agent
  NO  → Revise and re-test
        ↓
system-prompter agent approves
        ↓
Document the change (reason, token delta, benchmark delta)
        ↓
Deploy
```

---

*Prompts are code. They deserve the same rigour as code: structure, testing, version control, and review.*
