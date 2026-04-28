# Git Workflow

## Commit Messages — Conventional Commits

Format: `type(scope): description`

```
feat(retrieval): add MedCPT cross-encoder reranking for PubMed results
fix(formatter): correct citation numbering when response spans multiple WhatsApp messages
test(citation-verifier): add unit tests for orphaned citation detection
docs(ncbi): document double-negative human filter strategy
refactor(query-router): extract PICO parser into separate module
chore(deps): pin qdrant-client to 1.11.0
perf(embedding): batch BGE-M3 encoding to reduce T4 GPU memory pressure
```

**Types:** `feat` `fix` `test` `docs` `refactor` `chore` `perf` `ci` `build`

**Rules:**
- Present tense ("add" not "added")
- No period at end
- Body explains WHY, not WHAT (the diff shows what)
- Reference issue number if applicable: `fix(formatter): correct citation numbering (fixes #47)`

## Branch Naming

```
feature/add-medcpt-reranker
fix/citation-numbering-bug
chore/upgrade-qdrant-client
experiment/minicheck-integration
```

## Pull Request Standards

**Title:** Same format as commit message

**Description must include:**
1. What changed and why
2. How to test it (or why tests aren't needed)
3. Benchmark results if RAG pipeline changed (`Before: 6/10 queries pass → After: 8/10`)
4. Any migration steps required

**Size:** PRs > 400 lines of changed code should be split. Large PRs don't get reviewed properly.

## What Never Goes in Git

- API keys, tokens, passwords (use `.env`, `.gitignore` enforces this)
- Personal data / patient data
- Large binary files (use Cloud Storage)
- Generated files that can be rebuilt (`__pycache__`, `.pyc`, build artifacts)

## Pre-commit Hooks (enforce automatically)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks:
      - id: detect-private-key    # Catch API keys
      - id: check-json            # Valid JSON
      - id: trailing-whitespace
      - id: end-of-file-fixer
  
  - repo: https://github.com/psf/black
    hooks:
      - id: black                 # Python formatter (non-negotiable)
  
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff                  # Fast Python linter
      - id: ruff-format
```
