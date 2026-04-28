# Noocyte Skills — Production AI Engineering Kit

A complete set of skills, agents, rules, commands, hooks, and context files for building production-grade Python AI systems. Built for Noocyte.ai but structured to be **widely reusable** for any RAG pipeline, medical AI system, or Python API project.

---

## What's Inside

```
noocyte-skills-v2/
├── CLAUDE.md          ← Project config (Claude Code reads this first)
├── AGENTS.md          ← Delegation guide for all sub-agents
│
├── agents/            ← 13 specialist sub-agents for delegation
├── skills/            ← 16 workflow skills with complete code examples
├── commands/          ← 8 slash commands (/python-review, /tdd, /plan, etc.)
├── rules/             ← Always-on coding standards
├── hooks/             ← Session lifecycle and pre-commit automation
├── contexts/          ← Mode-specific context injection
└── examples/          ← Complete project CLAUDE.md examples
```

---

## Installation

### Option 1: Copy to your project

```bash
# Copy everything into your project's .claude directory
cp -r noocyte-skills-v2/agents .claude/
cp -r noocyte-skills-v2/skills .claude/
cp -r noocyte-skills-v2/commands .claude/
cp -r noocyte-skills-v2/rules .claude/
cp noocyte-skills-v2/CLAUDE.md .          # Or merge with existing CLAUDE.md
cp noocyte-skills-v2/AGENTS.md .
```

### Option 2: Use as skills.sh package (future)

```bash
npx skills add noocyte-ai/noocyte-skills
```

---

## The Agents (13 Specialists)

Load by saying: *"Read agents/[name].md and apply its review to [code/output]"*

| Agent | Use When |
|-------|---------|
| `planner` | Planning any multi-file feature |
| `architect` | Making technology decisions with trade-offs |
| `code-reviewer` | General code quality review |
| `senior-python-engineer` | Python-specific review (types, async, errors, logging) |
| `senior-ai-engineer` | RAG pipeline, LLM, embedding, citation review |
| `senior-medical-advisor` | Medical content safety and evidence quality |
| `security-reviewer` | Auth, input validation, prompt injection, secrets |
| `database-reviewer` | Qdrant, Redis, Firestore, PostgreSQL patterns |
| `harness-optimizer` | Benchmark evaluation and quality gate analysis |
| `build-error-resolver` | Python/GCP/Qdrant/asyncio build failures |
| `typescript-reviewer` | TypeScript type safety and async patterns |
| `e2e-runner` | End-to-end test design for async systems |
| `doc-updater-and-refactor-cleaner` | Documentation sync and code hygiene |

---

## The Skills (16 Workflow Guides with Code)

Triggered automatically when Claude Code detects relevant tasks.

### AI/RAG Core
- **`rag-pipeline`** — Complete pipeline: embedding → retrieval → reranking → generation → verification
- **`citation-verifier`** — P-Cite post-generation NLI entailment verification pipeline
- **`verification-loop`** — Generate → verify → correct → repeat patterns
- **`eval-harness`** — Evaluation framework with assertion-based test cases and RAGAS

### Data Sources
- **`ncbi-pubmed`** — PubMed E-utilities: rate limiting, ESearch/EFetch, MeSH, BioC full-text, CrossRef
- **`tavily-search`** — Live web retrieval with medical domain allowlists and hybrid Qdrant+Tavily
- **`medical-evidence-retrieval`** — PICO construction, source priority routing, Indian drug brand resolution, specialty-to-journal mapping

### Delivery
- **`whatsapp-formatter`** — 4096-char splitting, citation alignment in plain text, interactive buttons, Meta Cloud API

### Python Engineering
- **`python-patterns`** — Async, dataclasses, dependency injection, retry, structured logging
- **`python-testing`** — pytest fixtures, mock factories, async tests, TDD for AI systems
- **`tdd-workflow`** — Red-Green-Refactor with async and AI pipeline examples

### Infrastructure
- **`api-design`** — FastAPI patterns, error envelopes, pagination, status codes, webhooks
- **`deployment-patterns`** — Cloud Run, multi-stage Docker, GitHub Actions CI, zero-downtime rollback
- **`cost-aware-llm-pipeline`** — Model routing by complexity, token budgets, response caching, cost projection
- **`security-review`** — OWASP Top 10, prompt injection defence, rate limiting, PII redaction

### Content
- **`copywriting`** — Evidence-based copy for doctors, WhatsApp message templates, investor pitches
- **`article-writing`** — Long-form technical and medical writing without AI tone
- **`search-first`** — Research-before-coding workflow, library selection, ADR documentation

---

## The Commands (8 Slash Commands)

| Command | What It Does |
|---------|-------------|
| `/python-review` | Full Python review: types, async, error handling, AI-specific checks |
| `/build-fix` | Diagnose and fix build/runtime errors systematically |
| `/tdd` | Start Red-Green-Refactor cycle for a new function |
| `/plan` | Decompose feature into phased tasks with dependency graph |
| `/code-review` | General code quality review with severity levels |
| `/security-check` | OWASP + AI security audit |
| `/benchmark` | Run 10-query OpenEvidence evaluation harness |
| `/test-coverage` | Analyse gaps and generate missing tests |
| `/multi-plan` | Decompose into parallel workstreams with interfaces |
| `/multi-execute` | Orchestrate phased multi-workstream execution |

---

## Rules (Always-On)

Copy to `.claude/rules/` for automatic enforcement:

| Rule File | What It Enforces |
|-----------|-----------------|
| `common/always-on.md` | 17 non-negotiable rules: medical safety, citation integrity, rate limiting |
| `common/coding-style.md` | Naming, function size, comments, constants |
| `common/git-workflow.md` | Conventional commits, PR standards, pre-commit hooks |
| `common/testing.md` | Coverage targets, determinism, mock requirements |
| `python/python-rules.md` | Black+Ruff, type hints, async mandatory for I/O, Pydantic Settings |

---

## What Makes These Skills Different

Most skill collections are generic — they could apply to any project. These are opinionated:

**Medical AI constraints are built in.** The `always-on.md` rules, `senior-medical-advisor`, and citation verification pipeline all encode the "never prescribe" constraint, emergency detection protocol, ICMR source priority, and Indian drug brand resolution as first-class concerns. You don't have to remember to check for these — the agents do it automatically.

**Every skill has complete, runnable code.** Not pseudocode or architecture diagrams — actual Python with imports, error handling, async patterns, and tests. Copy, paste, adapt.

**The failure modes are documented.** Every skill includes a "What NOT to Do" section with specific anti-patterns, the consequences of each mistake, and the fix. This is the accumulated cost of having made those mistakes.

---

## Adapting for Non-Medical Projects

These skills are reusable outside medical AI with minor adaptation:

- Remove `medical-evidence-retrieval` (domain-specific) and `senior-medical-advisor`
- Replace `always-on.md`'s medical constraints with your domain's constraints
- Keep everything else — the RAG, Python, API, deployment, and evaluation patterns apply universally

The NCBI/PubMed skill is useful for any project that needs biomedical literature. The citation verifier applies to any RAG system. The verification loop, eval harness, and cost-aware LLM pipeline are completely domain-agnostic.
