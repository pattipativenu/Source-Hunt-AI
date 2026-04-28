# /test-coverage

Analyze test coverage for the specified module or the entire project, then generate missing tests.

## Instructions

1. Run existing tests with coverage:
```bash
pytest tests/unit/ -v --cov=. --cov-report=term-missing --cov-report=json
```

2. Identify gaps using coverage report:
   - Functions with 0% coverage (highest priority)
   - Error handling branches (common miss)
   - Edge cases (empty input, None, max values)

3. Generate missing tests following `skills/python-testing/SKILL.md` patterns

4. Target coverage thresholds:
   - Unit tests: ≥ 80% line coverage
   - Critical paths (citation verifier, query router, emergency detection): ≥ 95%
   - External API wrappers: 100% of error paths tested

## Coverage Priority Order

1. **Emergency detection** — zero tolerance for untested paths
2. **Citation verification** — accuracy-critical
3. **Query router** — routes every request
4. **WhatsApp formatter** — customer-facing, character limit bugs are invisible
5. **Retrieval pipeline** — retrieval failures = empty responses
6. **Utility functions** — lowest priority but still need baseline coverage

## Output Format

```
## Coverage Report

Current: X%
Target: 80%
Gap: Y functions uncovered

### New Tests Generated
tests/unit/test_[module].py — [N] tests added

### Remaining Gaps (manual attention needed)
- [function] — requires real API call to test meaningfully
```
