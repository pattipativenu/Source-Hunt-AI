# Noocyte AI — Claude Code Project Guide

> **Current Sprint:** Week 1 of 4
> **Sprint Gate:** 4/10 benchmark queries passing
> **Project:** WhatsApp-native clinical decision support for Indian doctors

---

## What Is Noocyte AI?

Noocyte AI is a professional clinical search engine for doctors in India. A doctor sends a clinical question via WhatsApp. Noocyte AI retrieves peer-reviewed evidence, synthesises it, and returns a structured, cited answer — in under 10 seconds.

Think of it as Open Evidence, but built for the Indian clinical context: ICMR guidelines first, Indian drug brand names resolved, and delivered through the channel Indian doctors already use every day.

---

## How to Navigate This Project

This `.claude/` directory is the project's intelligence layer. Everything here tells Claude Code how to work on Noocyte AI correctly.

### Start Here

Before doing anything, read these files in order:

1. **This file** (you are reading it) — project overview and navigation
2. **`rules/always-on.md`** — the non-negotiable rules that apply to every response
3. **`rules/prompt-writing.md`** — how to write prompts (read before touching any prompt)

### When You Need an Agent

| Task | Agent to Use |
|------|-------------|
| Write or audit a system prompt | `agents/system-prompter.md` |
| Review code for medical safety | `agents/medical-code-reviewer.md` |
| Debug a failing pipeline step | `agents/debugger.md` |
| Check a feature against the blueprint | `agents/blueprint-manager.md` |
| Break down a complex task | `agents/task-analyzer.md` |
| Brainstormer for hard problems | `agents/brainstormer.md` |
| Coordinate multiple agents | `agents/chief-of-operations.md` |

### When You Need a Skill

| Task | Skill to Read |
|------|--------------|
| Write a system prompt | `skills/system-prompter/SKILL.md` |
| Handle Indian drug brand names | `skills/indian-context-resolver/SKILL.md` |
| Format a response for WhatsApp | `skills/whatsapp-ux-optimizer/SKILL.md` |
| Run the benchmark test | `skills/eval-benchmark/SKILL.md` |
| Audit for PII | `skills/pii-audit/SKILL.md` |
| Research a HuggingFace model | `skills/huggingface-research/SKILL.md` |
| Optimise a transformer/neural net | `skills/ml-model-optimizer/SKILL.md` |
| Engineer a context window | `skills/context-engineering/SKILL.md` |
| Debug a PyTorch/dependency issue | `skills/pytorch-resolver/SKILL.md` |
| Create a new skill automatically | `skills/skill-self-creator/SKILL.md` |
| Validate the architecture | `skills/blueprint-manager/SKILL.md` |
| Build an autonomous pipeline loop | `skills/autonomous-loop/SKILL.md` |

---

## The Pipeline (10 Steps)

Every query flows through exactly these steps:

```
1. Acute protocol check → if acute: prioritize golden-hour management, BLUF protocol
2. PII redaction → remove Aadhaar, phone, patient names
3. Indian context resolution → brand→INN internally, Hinglish normalisation
4. Query understanding → PICO extraction, intent classification
5. Parallel retrieval → Qdrant + PubMed + Tavily (conditional)
6. Two-tier reranking → Cohere Rerank 3.5 → MedCPT Cross-Encoder
7. Context assembly → lost-in-the-middle mitigation, source priority
8. Gemini 2.5 Flash → structured JSON, temperature=0.0
9. Citation verification → NLI entailment > 0.7, DOI validation
10. WhatsApp formatter → BLUF structure, message splitting, buttons
```

---

## The Technology Stack

| Component | Technology |
|-----------|-----------|
| Cloud | Google Cloud Platform |
| Compute | Cloud Run (serverless) |
| Message queue | Cloud Pub/Sub |
| Vector database | Qdrant (self-hosted) |
| Cache | Redis (Cloud Memorystore) |
| Analytics | BigQuery |
| Primary LLM | Gemini 2.5 Flash |
| Embedding | BAAI/BGE-M3 |
| Reranker 1 | Cohere Rerank 3.5 |
| Reranker 2 | ncats/MedCPT-Cross-Encoder |
| NLI verifier | MoritzLaurer/DeBERTa-v3-large |
| WhatsApp | Meta Cloud API |
| Backend | FastAPI + Python 3.11 |

---

## The 4-Week Sprint Plan

```
Week 1: Core RAG pipeline end-to-end
  Gate: 4/10 benchmark queries pass
  
Week 2: WhatsApp integration
  Gate: 5/10 benchmark + round-trip < 10s
  
Week 3: India-aware responses
  Gate: 7/10 benchmark queries pass
  
Week 4: Production-ready soft launch
  Gate: 9/10 benchmark + Meta Business Verification
```

---

## The 10 Benchmark Queries

The quality bar is set by 10 OpenEvidence-style queries. Full gold-standard answers are in `skills/eval-benchmark/openevidence-gold-standard.md`.

Run the benchmark:
```bash
python3 scripts/run_benchmark.py --queries tests/benchmark/openevidence_10.json
```

---

## Non-Negotiable Rules (Summary)

Full rules are in `rules/always-on.md`. The summary:

1. **No prescriptive language** — never "prescribe", "administer", "give the patient"
2. **Every factual claim cited** — every %, HR, p-value has an inline [N]
3. **Acute protocol priority** — for emergencies, give evidence-based protocols first
4. **PII redacted before logging** — ensure search logs contain only clinical data
5. **Temperature ≤ 0.1** — for all medical generation
6. **ICMR first** — for Indian conditions
7. **Structured JSON always** — no plain text medical responses
8. **Absolute brand neutrality** — use ONLY the generic (INN) name in the final output

---

## Project Context for Non-Technical Founders

You do not need a computer science background to work on this project. Here is what you need to know:

**What Claude Code does:** It reads the files in this `.claude/` directory to understand how to help you. The agents tell it what roles to play. The skills tell it how to do specific tasks. The rules tell it what it must never do.

**What you do:** You describe what you want in plain language. Claude Code reads the right skill or agent, follows the instructions, and produces the result. You review it, approve it, and it gets pushed to GitHub.

**The most important thing:** Every time something is built, it is tested against the 10 benchmark queries. If the score goes up, the change is good. If it goes down, it is reverted. The benchmark is the truth.

---

*Noocyte AI exists to give Indian doctors fast, accurate, cited clinical answers — through the channel they already use, in the context they actually work in.*
