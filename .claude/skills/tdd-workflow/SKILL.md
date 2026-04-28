---
name: tdd-workflow
description: Use this skill when writing any new function, class, or module using Test-Driven Development — write failing tests first, implement to make them pass, refactor. Also trigger for: "write tests first", "red-green-refactor", "TDD", "failing tests before implementation", designing APIs through tests. Applies to any language or project.
---

# TDD Workflow — Red, Green, Refactor

TDD is not about testing after the fact. It is a **design discipline** that forces clarity about what a function must do before you think about how to do it. The test IS the specification.

## The Three Laws of TDD

1. Write NO production code until you have a failing test for it
2. Write NO more test code than is sufficient to fail (including compilation failures)
3. Write NO more production code than is sufficient to pass the failing test

Breaking these laws is how TDD becomes "test after" — which is entirely different and much less valuable.

---

## The Red-Green-Refactor Cycle

```
RED: Write the smallest failing test
  ↓
GREEN: Write the minimum code to make it pass
  ↓
REFACTOR: Clean up without breaking tests
  ↓
(repeat)
```

The entire cycle should take 2-5 minutes per iteration. If a cycle takes longer, your steps are too large.

---

## Python TDD Example: Citation Verifier

### Step 1: RED — Write the smallest failing test

```python
# tests/unit/test_citation_verifier.py

def test_verify_claim_passes_high_confidence():
    """A claim with confidence > 0.7 should pass verification."""
    # Arrange
    claim = "Fidaxomicin is preferred for CDI"
    source = "IDSA 2021 guidelines recommend fidaxomicin as first-line therapy."
    
    # Act
    result = verify_claim(claim, source, threshold=0.7)
    
    # Assert
    assert result["passes"] is True
```

Run: `pytest tests/unit/test_citation_verifier.py` → **RED (ImportError: verify_claim)**

### Step 2: Create the stub (minimum to get to a better failure)

```python
# src/citation_verifier.py

def verify_claim(claim: str, source: str, threshold: float = 0.7) -> dict:
    raise NotImplementedError
```

Run: → **RED (NotImplementedError)**

### Step 3: Implement minimum to pass

```python
def verify_claim(claim: str, source: str, threshold: float = 0.7) -> dict:
    # Minimum implementation: check if claim words appear in source
    claim_words = set(claim.lower().split())
    source_words = set(source.lower().split())
    overlap = len(claim_words & source_words) / len(claim_words)
    confidence = overlap  # Simple lexical overlap as MVP
    
    return {
        "confidence": confidence,
        "passes": confidence >= threshold,
    }
```

Run: → **GREEN** ✅

### Step 4: Add next failing test (low confidence)

```python
def test_verify_claim_fails_low_confidence():
    """A claim with no support in source should fail."""
    claim = "Fidaxomicin reduces mortality by 50%"
    source = "Vancomycin is an alternative for CDI treatment."
    
    result = verify_claim(claim, source, threshold=0.7)
    
    assert result["passes"] is False
    assert result["confidence"] < 0.7
```

Run: → check if GREEN or RED. Iterate.

### Step 5: Refactor when both tests pass

Only refactor in the GREEN state. If tests pass:
- Extract magic numbers to named constants
- Add type hints
- Improve variable names
- Split if functions are > 20 lines

---

## TDD for Async Functions

```python
@pytest.mark.asyncio
async def test_pubmed_search_returns_abstracts_for_valid_query():
    """PubMed search for known CDI query should return at least one result."""
    # Use mock NCBI client — never call real API in unit tests
    mock_client = create_mock_ncbi_client(
        esearch_result={"count": "5", "webenv": "test_env", "querykey": "1"},
        efetch_result=SAMPLE_PUBMED_XML,
    )
    
    results = await search_pubmed(
        client=mock_client,
        query="Clostridioides difficile treatment",
        max_results=5,
    )
    
    assert len(results) >= 1
    assert all("pmid" in r for r in results)
    assert all("abstract" in r for r in results)
```

---

## TDD Design Benefits

When you write the test first, you discover:

1. **Hard-to-test code is hard to use.** If writing the test is painful, the API is wrong. Fix the API.
2. **Dependencies become explicit.** Tests reveal hidden global state and tight coupling.
3. **Acceptance criteria are clarified.** You can't write a test for a vague requirement.

---

## What NOT to Do

```python
# ❌ Writing tests AFTER implementation to hit coverage
# These tests validate what was built, not what should be built
# They contain none of the design pressure that TDD provides

# ❌ One giant test with many assertions
def test_everything():
    result = full_pipeline(query)
    assert result.citations
    assert result.answer
    assert result.latency < 15000
    # When this fails, you don't know which assertion failed or why

# ✅ One test, one assertion, clear name
def test_pipeline_returns_at_least_two_citations_for_guideline_query():
    result = full_pipeline("CDI first-line treatment")
    assert len(result.citations) >= 2

# ❌ Mocking so deeply that the test doesn't test anything
# If you mock the function being tested, you test nothing
mock.patch("mymodule.verify_claim", return_value={"passes": True})
result = verify_claim("anything")  # Always passes — pointless
```

---

## When TDD is Harder (and What To Do)

**Exploratory code:** When you don't know what the API should be, spike first (no tests), then TDD the real implementation.

**Complex integration:** TDD individual components. Integration tests come after the components work.

**External API wrappers:** Write contract tests (test the expected interface) and stub the actual API. TDD the retry/error logic.
