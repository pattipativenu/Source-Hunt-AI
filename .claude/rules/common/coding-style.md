# Coding Style — Language-Agnostic Principles

These rules apply to every codebase regardless of language.

## Naming

- **Names describe what things ARE or DO** — not how they work internally
- **Booleans are questions:** `is_verified`, `has_citations`, `can_retry` — not `verified`, `citations`, `retry`
- **Functions are verbs:** `fetch_articles()`, `build_query()`, `validate_doi()` — not `articles()`, `query()`
- **Avoid abbreviations** unless universally understood: `url`, `id`, `api` are fine; `rtrv_art` is not
- **Consistency over cleverness** — use the same name for the same concept everywhere

## Functions

- **One function, one responsibility** — if you can't name a function without "and", split it
- **Functions < 30 lines** — if longer, it's doing too much
- **Maximum 3 parameters** — more than 3 suggests passing a config object
- **No side effects in query functions** — functions that return values should not mutate state

## Comments

```python
# ❌ Comments that describe WHAT (the code already says this)
x = x + 1  # Increment x

# ✅ Comments that explain WHY (the code can't say this)
x = x + 1  # Offset by 1 because NCBI uses 1-indexed pagination

# ❌ Commented-out code — use version control
# old_function()

# ✅ TODO with owner and ticket
# TODO(eng-123): Replace Gemini-as-judge with MiniCheck at 500+ DAUs
```

## File Organisation

- One class or logical group per file
- Files < 300 lines — split when approaching this limit
- Related files in a directory; directory name describes the domain
- No circular imports — if A imports B and B imports A, something is wrong

## Constants and Magic Numbers

```python
# ❌ Magic number with no explanation
if len(candidates) > 50:
    candidates = candidates[:50]

# ✅ Named constant
MAX_RERANKING_CANDIDATES = 50  # Cohere reranking degrades above this

if len(candidates) > MAX_RERANKING_CANDIDATES:
    candidates = candidates[:MAX_RERANKING_CANDIDATES]
```

## Error Messages

Error messages have ONE audience: the engineer debugging at 2am.

- State what failed: `"ESearch returned 0 results"`
- State what was expected: `"Expected at least 1 result for query: {query}"`
- State what to do: `"Check NCBI API key and rate limiter"`

Never: `"An error occurred"` — this is information-free.

## Dead Code

Delete it. Version control is for history. Code is for the present.
