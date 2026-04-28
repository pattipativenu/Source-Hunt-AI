# Example: Python FastAPI + Qdrant RAG Project

This is an example CLAUDE.md showing how to adapt the noocyte-skills for a generic RAG project (not medical-specific).

Copy this to your project root and replace the Noocyte-specific sections with your own.

---

# [Your Project Name] — Claude Code Project Configuration

## What We're Building

[One paragraph: what the project is, who it's for, what problem it solves]

**Stack:** Python 3.11 · FastAPI · Qdrant Cloud · [Your embedding model] · Gemini 2.5 Flash · GCP Cloud Run

---

## Non-Negotiable Constraints

[List your project's hard constraints here — things that are never negotiable]

1. **[Domain constraint 1]** — e.g., "Never expose user PII in logs"
2. **[Domain constraint 2]** — e.g., "All LLM outputs must cite sources"
3. **API rate limits:** [Your external API rate limits here]
4. **Response format:** [Your output format constraints]

---

## Data Flow

```
[Entry point] → [Processing] → [Output]
```

Describe your data flow here.

---

## Environment Variables

```bash
QDRANT_URL=
QDRANT_API_KEY=
GEMINI_API_KEY=
COHERE_API_KEY=
```

---

## Agents Available

Same agents as noocyte-skills — all reusable. The only domain-specific agent is `senior-medical-advisor` which you should replace with your domain expert.

| Task | Agent |
|------|-------|
| Planning | `agents/planner.md` |
| Python review | `agents/senior-python-engineer.md` |
| RAG/LLM review | `agents/senior-ai-engineer.md` |
| Security | `agents/security-reviewer.md` |
| Database | `agents/database-reviewer.md` |
| Build errors | `agents/build-error-resolver.md` |
| Quality | `agents/harness-optimizer.md` |

---

## Quality Gates

```bash
pytest tests/unit/ --cov=. --cov-fail-under=80
mypy . --strict
ruff check .
python scripts/run_benchmark.py  # Your benchmark here
```

---

## Slash Commands

Same commands as noocyte-skills — all reusable.

| Command | When |
|---------|------|
| `/python-review` | After writing Python |
| `/build-fix` | On any error |
| `/tdd` | Starting new function |
| `/plan` | Before multi-file feature |
| `/benchmark` | Before merge |
