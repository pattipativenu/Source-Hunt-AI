# /build-fix

Diagnose and fix the current build/runtime error.

## Instructions

1. Read the full error message — scroll to the bottom for the root cause
2. Identify the error category from `agents/build-error-resolver.md`
3. Check environment (Python version, installed packages, env vars set)
4. Apply the minimum fix — one change at a time
5. Verify fix: re-run the failing command
6. Document in a comment why the fix works

## Output Format

```
## Error Category: [Import/Type/Async/GCP/Qdrant/etc.]

Root Cause: [One sentence]

Fix Applied:
[Code change or command]

Verification:
[Command to run to confirm fixed]

Note: [Why this happened and how to prevent it]
```
