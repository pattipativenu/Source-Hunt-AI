# Testing Standards

## Non-Negotiable Requirements

1. **New code without tests is not finished.** A function is incomplete without at least one test for the happy path and one for each error case.

2. **Tests must be deterministic.** No `time.sleep()`, no random seeds, no tests that pass sometimes and fail sometimes. Flaky tests destroy CI trust.

3. **External services must be mocked.** Unit and integration tests must not call real APIs (PubMed, Gemini, Cohere, Qdrant Cloud). Use `unittest.mock`, `pytest-mock`, or test fixtures.

4. **The 10-query benchmark must pass before any merge** that changes the RAG pipeline, system prompt, retrieval config, or generation parameters.

## Coverage Targets

| Component | Minimum Coverage | Rationale |
|-----------|-----------------|-----------|
| Emergency detection | 100% | Zero tolerance — life-critical |
| Citation verifier | 95% | Accuracy-critical |
| Query router | 90% | Every request flows through here |
| WhatsApp formatter | 85% | Customer-facing |
| Retrieval pipeline | 80% | Core functionality |
| API endpoints | 80% | Interface contract |
| Utility functions | 75% | Supporting code |

## Test Naming Convention

Tests must describe what they test, not what the function is:

```python
# ❌ Describes implementation
def test_verify_claim():

# ✅ Describes behaviour
def test_verify_claim_returns_false_when_source_does_not_support_claim():
def test_query_router_routes_emergency_without_calling_llm():
def test_formatter_splits_message_at_paragraph_boundary_not_mid_word():
```

## Test Structure (Arrange-Act-Assert)

```python
def test_citation_verifier_removes_unsupported_claims():
    # Arrange
    answer = "Fidaxomicin reduces recurrence [1]. It also cures cancer [2]."
    supported_claim = "Fidaxomicin reduces recurrence"
    unsupported_claim = "It also cures cancer"
    references = [...]
    
    # Act
    result = verify_and_clean(answer, references)
    
    # Assert
    assert supported_claim in result["answer"]
    assert unsupported_claim not in result["answer"]
    assert result["pass_rate"] == 0.5
```

## Pytest Configuration

```ini
[tool.pytest.ini_options]
asyncio_mode = "auto"          # Auto-handle async tests
testpaths = ["tests"]
markers = [
    "unit: fast, no external dependencies",
    "integration: requires test infrastructure",
    "e2e: runs full pipeline (slow, use sparingly)",
    "benchmark: runs 10-query OpenEvidence harness",
]

# Run subsets:
# pytest -m unit        → fastest, run on every save
# pytest -m integration → run on every PR
# pytest -m benchmark   → run before merge to main
```
