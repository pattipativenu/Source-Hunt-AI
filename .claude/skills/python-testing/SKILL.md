---
name: python-testing
description: Use this skill when writing, reviewing, or improving Python tests — including unit tests, integration tests, async tests, mocking external APIs, testing LLM pipelines, fixture design, and test coverage analysis with pytest. Also trigger for: TDD workflow, test structure review, flaky tests, mocking httpx/requests/qdrant/gemini, parametrize patterns, and test-driven development for AI systems. Applies to any Python project.
---

# Python Testing — pytest Patterns for Production Systems

## The Test Pyramid for AI Systems

```
         [E2E Tests — slow, few]
        /  Full pipeline with real APIs  \
       /     (run weekly, not on every PR) \
      /-----------------------------------\
     [Integration Tests — medium speed]
    /  Real DB + mocked external APIs      \
   /   (run on every PR, ~2 min budget)     \
  /-------------------------------------------\
 [Unit Tests — fast, many]
/  Pure functions, mocked everything external  \
/ (run on every commit, <30 seconds)            \
```

For AI/RAG systems specifically:
- **Unit**: Query parser, chunk builder, response formatter, MeSH query builder
- **Integration**: Full retrieval pipeline with Qdrant test instance
- **E2E**: Complete query → response pipeline against the 10-query benchmark

---

## Project Structure

```
tests/
├── conftest.py              # Shared fixtures and mock factories
├── unit/
│   ├── test_query_router.py
│   ├── test_chunker.py
│   ├── test_formatter.py
│   └── test_citation_verifier.py
├── integration/
│   ├── test_retrieval_pipeline.py
│   └── test_pubmed_client.py
└── e2e/
    └── test_benchmark.py    # 10-query OpenEvidence benchmark
```

---

## Core Testing Patterns

### conftest.py — Shared Fixtures

```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# ---- Mock factories ----

@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client with realistic return values."""
    client = MagicMock()
    
    # Mock search results
    mock_point = MagicMock()
    mock_point.payload = {
        "content": "Fidaxomicin is preferred over vancomycin for CDI based on IDSA 2021 guidelines.",
        "source": "ICMR",
        "pub_year": 2021,
        "evidence_level": "Guideline",
        "source_tier": 1,
    }
    mock_point.score = 0.92
    
    client.search.return_value = [mock_point]
    client.query_points.return_value.points = [mock_point]
    return client


@pytest.fixture
def mock_gemini_model():
    """Mock Gemini model with realistic medical response."""
    model = MagicMock()
    model.generate_content_async = AsyncMock(return_value=MagicMock(
        text='''{
            "answer": "IDSA/SHEA 2021 guidelines recommend fidaxomicin 200mg PO BID for 10 days [1].",
            "clinical_bottom_line": "Fidaxomicin is preferred over vancomycin due to lower recurrence rates.",
            "evidence_quality": "high",
            "claims": [{"text": "fidaxomicin 200mg PO BID recommended", "citations": [{"ref_id": 1, "confidence": 0.94}]}],
            "references": [{"id": 1, "authors": "Johnson S et al.", "title": "IDSA/SHEA CDI Guidelines", "journal": "Clin Infect Dis", "year": 2021, "doi": "10.1093/cid/ciab549"}]
        }'''
    ))
    return model


@pytest.fixture
def mock_ncbi_client():
    """Mock httpx client for PubMed E-utilities."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get.return_value = MagicMock(
        status_code=200,
        json=lambda: {
            "esearchresult": {
                "count": "1",
                "webenv": "MCID_test_env",
                "querykey": "1",
                "idlist": ["34164674"],
            }
        },
    )
    return client


@pytest.fixture
def sample_query() -> str:
    return "What is the first-line treatment for CDI in adults?"


@pytest.fixture
def sample_chunks() -> list[dict]:
    return [
        {
            "content": "Fidaxomicin 200mg BID for 10 days is recommended as first-line therapy. Vancomycin is acceptable when fidaxomicin is unavailable.",
            "source": "IDSA/SHEA 2021",
            "pub_year": 2021,
            "score": 0.92,
        },
        {
            "content": "Meta-analysis of 3,944 patients found fidaxomicin reduced recurrence by 31% vs vancomycin (RR 0.69, 95% CI 0.52-0.91).",
            "source": "Liao et al, Pharmacotherapy 2022",
            "pub_year": 2022,
            "score": 0.87,
        },
    ]
```

---

### Unit Tests — Query Router

```python
import pytest
from myapp.core.query_router import (
    classify_query, detect_emergency, detect_brand_name, expand_query,
    QueryIntent, ResponseMode,
)

class TestEmergencyDetection:
    @pytest.mark.parametrize("query,expected", [
        ("patient in cardiac arrest", True),
        ("STEMI management guidelines", True),
        ("anaphylactic shock protocol", True),
        ("first-line treatment for CDI", False),
        ("what is the dose of amoxicillin", False),
    ])
    def test_emergency_keywords(self, query: str, expected: bool):
        result = detect_emergency(query)
        assert (result is not None) == expected
    
    def test_emergency_message_contains_helpline(self):
        msg = detect_emergency("cardiac arrest management")
        assert "108" in msg  # Indian emergency number


class TestBrandNameDetection:
    @pytest.mark.parametrize("query,expected_brand,expected_generic", [
        ("what is dolo 650 used for", "dolo", "Paracetamol (Acetaminophen)"),
        ("augmentin dose for pneumonia", "augmentin", "Amoxicillin + Clavulanic Acid"),
        ("metformin dose for T2DM", None, None),  # INN, not a brand
    ])
    def test_brand_detection(self, query, expected_brand, expected_generic):
        brand, generic = detect_brand_name(query)
        assert brand == expected_brand
        assert generic == expected_generic


class TestQueryExpansion:
    def test_expands_abbreviations(self):
        expanded = expand_query("Rx for DM with CKD")
        assert "treatment" in expanded.lower()
        assert "diabetes mellitus" in expanded.lower()
        assert "chronic kidney disease" in expanded.lower()
    
    def test_preserves_original_if_no_abbreviations(self):
        query = "first-line treatment for hypertension"
        expanded = expand_query(query)
        assert "hypertension" in expanded


@pytest.mark.asyncio
class TestClassifyQuery:
    async def test_drug_lookup_intent(self, mock_gemini_model):
        with patch("myapp.core.query_router.get_gemini_model", return_value=mock_gemini_model):
            mock_gemini_model.generate_content_async.return_value = MagicMock(
                text='{"intent": "drug_lookup", "response_mode": "quick", "data_sources": ["drug_db"], "pico": {}, "search_queries": ["Dolo Paracetamol"], "confidence": 0.9}'
            )
            result = await classify_query("what is dolo 650?")
        
        assert result.intent == QueryIntent.DRUG_LOOKUP
        assert result.response_mode == ResponseMode.QUICK
        assert "drug_db" in result.data_sources
    
    async def test_emergency_bypass_llm(self):
        """Emergency detection must NOT call the LLM — it's time-critical."""
        with patch("myapp.core.query_router.classify_with_llm") as mock_llm:
            result = await classify_query("cardiac arrest management")
        
        assert result.is_emergency is True
        mock_llm.assert_not_called()  # LLM should never be called for emergencies
```

---

### Unit Tests — Citation Verifier

```python
@pytest.mark.asyncio
class TestCitationVerifier:
    async def test_high_confidence_claim_passes(self, mock_gemini_model):
        mock_gemini_model.generate_content_async.return_value = MagicMock(
            text='{"entailment": true, "confidence": 0.94, "reason": "Source directly states fidaxomicin is preferred"}'
        )
        
        result = await verify_claim(
            claim_text="Fidaxomicin is preferred first-line for CDI",
            source_passage="IDSA/SHEA 2021 recommends fidaxomicin as first-line therapy for initial CDI.",
            model=mock_gemini_model,
        )
        
        assert result["entailment"] is True
        assert result["confidence"] == 0.94
        assert result["passes"] is True
    
    async def test_low_confidence_claim_fails(self, mock_gemini_model):
        mock_gemini_model.generate_content_async.return_value = MagicMock(
            text='{"entailment": false, "confidence": 0.2, "reason": "Source does not mention recurrence rates"}'
        )
        
        result = await verify_claim(
            claim_text="Fidaxomicin reduces recurrence by 50%",
            source_passage="Fidaxomicin is effective for CDI treatment.",
            model=mock_gemini_model,
        )
        
        assert result["passes"] is False
    
    async def test_prescriptive_language_detection(self):
        """Verify that prescriptive language is caught."""
        prescriptive_claims = [
            "Give fidaxomicin 200mg BID",
            "Prescribe vancomycin for this patient",
            "Administer IV antibiotics immediately",
        ]
        
        for claim in prescriptive_claims:
            has_prescriptive = contains_prescriptive_language(claim)
            assert has_prescriptive, f"Failed to detect prescriptive language in: {claim}"
```

---

### Integration Tests — Retrieval Pipeline

```python
@pytest.mark.asyncio
@pytest.mark.integration  # Mark so they can be skipped in fast CI
class TestRetrievalPipeline:
    """
    Tests the full retrieval pipeline with mocked external APIs
    but real internal logic.
    """
    
    async def test_full_retrieval_returns_ranked_chunks(
        self, mock_qdrant_client, mock_ncbi_client, sample_query
    ):
        results = await hybrid_retrieve(
            query=sample_query,
            qdrant_client=mock_qdrant_client,
            max_results=5,
        )
        
        assert len(results) > 0
        assert all("content" in r for r in results)
        # Results must be sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
    
    async def test_empty_query_returns_empty_list(self, mock_qdrant_client):
        mock_qdrant_client.search.return_value = []
        results = await hybrid_retrieve(query="", qdrant_client=mock_qdrant_client)
        assert results == []
    
    async def test_retrieval_excludes_animal_studies(self, mock_ncbi_client):
        """Verify Humans[MeSH] filter is applied."""
        search_result = await search_pubmed_with_client(
            client=mock_ncbi_client,
            query="CDI treatment",
        )
        
        # Check that the actual query sent to NCBI includes human filter
        call_args = mock_ncbi_client.get.call_args
        query_params = call_args[1]["params"]["term"]
        assert "NOT (animals[MeSH] NOT humans[MeSH])" in query_params
```

---

### E2E Benchmark Tests

```python
BENCHMARK_QUERIES = [
    {
        "id": 1,
        "query": "First-line treatment for CDI in adults per IDSA 2021",
        "min_citations": 2,
        "required_terms": ["fidaxomicin", "vancomycin", "recurrence"],
        "forbidden_phrases": ["prescribe", "give the patient", "I recommend"],
    },
    # ... all 10 queries
]

@pytest.mark.e2e
@pytest.mark.parametrize("test_case", BENCHMARK_QUERIES, ids=[q["id"] for q in BENCHMARK_QUERIES])
async def test_benchmark_query(test_case, full_pipeline):
    response = await full_pipeline.process(test_case["query"])
    
    # Check citation count
    citations = re.findall(r"\[(\d+)\]", response.answer)
    assert len(set(citations)) >= test_case["min_citations"], \
        f"Expected {test_case['min_citations']} citations, got {len(set(citations))}"
    
    # Check required terms
    for term in test_case["required_terms"]:
        assert term.lower() in response.answer.lower(), \
            f"Missing required term: {term}"
    
    # Check forbidden phrases (prescriptive language)
    for phrase in test_case["forbidden_phrases"]:
        assert phrase.lower() not in response.answer.lower(), \
            f"Prescriptive language detected: {phrase}"
    
    # Check citation-reference alignment
    ref_ids = {r.id for r in response.references}
    inline_ids = {int(c) for c in citations}
    orphaned = inline_ids - ref_ids
    assert not orphaned, f"Inline citations without references: {orphaned}"
```

---

## Coverage Requirements

```ini
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "integration: requires test database",
    "e2e: runs full pipeline (slow)",
]

[tool.coverage.run]
omit = ["tests/*", "scripts/*"]

[tool.coverage.report]
fail_under = 80  # Minimum 80% coverage
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

Run with:
```bash
pytest tests/unit/ -v --cov=myapp --cov-report=term-missing
pytest tests/integration/ -v -m integration
pytest tests/e2e/ -v -m e2e --timeout=60
```
