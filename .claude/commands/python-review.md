# /python-review

Perform a thorough review of the Python code provided or currently in context.

## Instructions

1. Load the `senior-python-engineer` agent from `agents/senior-python-engineer.md`
2. Load the `senior-ai-engineer` agent from `agents/senior-ai-engineer.md` if the code relates to ML, RAG, or LLM pipelines
3. Review the code against ALL checklist items in those agents
4. Structure output as:

```
## Python Review

### Critical (must fix before merge)
- [Issue] [File:line] — [Why it matters] [Suggested fix]

### Major (fix in this PR)
- ...

### Minor (fix in follow-up)
- ...

### Approved ✓
- [What's done well]
```

## What Always Gets Checked

- Type hints on all functions (parameters + return types)
- Exception handling — specific exceptions, logged, re-raised properly
- Async code — no blocking calls in async context, `return_exceptions=True` in gather
- Rate limiting on external API calls (NCBI = 10 req/s)
- Configuration from environment variables, not hardcoded
- No `print()` in production code — use `logging`
- Retry decorator on external network calls
- Resource cleanup with context managers
- Tests exist for new functions

## AI/RAG-Specific Checks (if applicable)

- Temperature ≤ 0.1 for factual generation
- Structured JSON output enforced
- Context window management (5-10 chunks, not 20+)
- Citation verification step present
- No prescriptive language in medical output
- Human-only MeSH filter on PubMed queries
- PII redaction on logged data
