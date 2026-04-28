---
name: eval-harness
description: Use this skill when building evaluation frameworks for AI systems — defining quality criteria, writing test cases with expected outputs, running evaluations against defined metrics, tracking regressions, and producing evaluation reports. Also trigger for: LLM evaluation, benchmark design, quality gates, RAGAS setup, assertion-based testing for AI outputs, grading rubrics for subjective outputs. Applies to any AI/LLM system that needs measurable quality assurance.
---

# Eval Harness — Measuring AI System Quality

You cannot improve what you cannot measure. An eval harness is a system that runs your AI pipeline against curated inputs and scores the outputs against defined criteria, producing a consistent quality signal you can track over time.

The key property of a good harness: **it catches regressions before users do.**

---

## Eval Harness Architecture

```
Test Cases (JSON)
    ↓
Harness Runner (async, parallel execution)
    ↓
Pipeline Under Test
    ↓
Output Collector
    ↓
Scorer (per-dimension)
    ↓
Aggregator + Report
    ↓
Quality Gate (pass/fail)
```

---

## Test Case Design

A test case is a tuple of: `(input, expected_properties)`. For RAG systems, expected_properties are assertions about the output — not exact expected output (LLMs are non-deterministic).

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class EvalAssertion:
    """A single verifiable claim about the output."""
    name: str
    check: str           # What to check: "contains" | "not_contains" | "min_count" | "schema" | "custom"
    value: Any           # Expected value or threshold
    weight: float = 1.0  # Relative importance
    zero_tolerance: bool = False  # If True, any failure = overall fail regardless of score

@dataclass
class EvalTestCase:
    """A single evaluation test case."""
    id: str
    name: str
    input: str | dict
    difficulty: str      # "easy" | "medium" | "hard"
    assertions: list[EvalAssertion]
    tags: list[str] = field(default_factory=list)
    notes: str = ""


# Test case library — build once, run forever
NOOCYTE_TEST_CASES = [
    EvalTestCase(
        id="CDI-001",
        name="CDI first-line treatment (IDSA 2021)",
        difficulty="easy",
        input="What is the preferred first-line treatment for initial non-fulminant CDI in adults?",
        assertions=[
            EvalAssertion("has_citations", "min_count", 2, weight=1.5),
            EvalAssertion("citation_alignment", "custom", "all_inline_cite_ids_have_references", weight=2.0, zero_tolerance=True),
            EvalAssertion("mentions_fidaxomicin", "contains", "fidaxomicin", weight=1.0),
            EvalAssertion("mentions_vancomycin", "contains", "vancomycin", weight=1.0),
            EvalAssertion("no_prescriptive_language", "not_contains_any", ["prescribe", "give the patient", "administer"], weight=2.0, zero_tolerance=True),
            EvalAssertion("cites_idsa_or_shea", "contains_any", ["IDSA", "SHEA", "Johnson S"], weight=1.5),
            EvalAssertion("latency_ok", "max_value", 15000, weight=0.5),
        ],
        tags=["infectious_disease", "guidelines", "treatment"],
    ),
    EvalTestCase(
        id="AF-CKD-001",
        name="Apixaban vs Rivaroxaban in AF with CKD",
        difficulty="medium",
        input="Compare apixaban and rivaroxaban for stroke prevention in AF with moderate CKD (eGFR 30-50)",
        assertions=[
            EvalAssertion("has_citations", "min_count", 4, weight=1.5),
            EvalAssertion("citation_alignment", "custom", "all_inline_cite_ids_have_references", zero_tolerance=True),
            EvalAssertion("mentions_apixaban", "contains", "apixaban"),
            EvalAssertion("mentions_rivaroxaban", "contains", "rivaroxaban"),
            EvalAssertion("addresses_ckd", "contains_any", ["CKD", "chronic kidney", "eGFR", "renal"]),
            EvalAssertion("addresses_bleeding", "contains_any", ["bleeding", "hemorrhage", "haemorrhage"]),
            EvalAssertion("no_prescriptive_language", "not_contains_any", ["prescribe", "switch to", "recommend switching"], zero_tolerance=True),
            EvalAssertion("cites_guideline", "contains_any", ["ACC", "AHA", "JACC", "ESC"]),
        ],
        tags=["cardiology", "nephrology", "comparison", "medium"],
    ),
    # ... remaining 8 queries from OpenEvidence benchmark
]
```

---

## Scorer Implementation

```python
import re
import time
from typing import Any

@dataclass
class AssertionResult:
    assertion_name: str
    passed: bool
    score: float
    actual_value: Any
    message: str

class EvalScorer:
    """Scores pipeline output against a test case's assertions."""
    
    def score_output(
        self,
        test_case: EvalTestCase,
        output: dict,
        latency_ms: float,
    ) -> list[AssertionResult]:
        results = []
        
        answer = output.get("answer", "")
        references = output.get("references", [])
        
        for assertion in test_case.assertions:
            result = self._check_assertion(assertion, answer, references, latency_ms)
            results.append(result)
        
        return results
    
    def _check_assertion(
        self,
        assertion: EvalAssertion,
        answer: str,
        references: list[dict],
        latency_ms: float,
    ) -> AssertionResult:
        answer_lower = answer.lower()
        
        match assertion.check:
            case "contains":
                passed = assertion.value.lower() in answer_lower
                return AssertionResult(
                    assertion_name=assertion.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    actual_value=assertion.value in answer,
                    message=f"{'Found' if passed else 'Missing'}: {assertion.value}",
                )
            
            case "not_contains_any":
                found = [v for v in assertion.value if v.lower() in answer_lower]
                passed = len(found) == 0
                return AssertionResult(
                    assertion_name=assertion.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    actual_value=found,
                    message=f"Forbidden phrases found: {found}" if not passed else "Clean",
                )
            
            case "contains_any":
                found = [v for v in assertion.value if v.lower() in answer_lower]
                passed = len(found) > 0
                return AssertionResult(
                    assertion_name=assertion.name,
                    passed=passed,
                    score=1.0 if passed else 0.0,
                    actual_value=found,
                    message=f"Found: {found}" if passed else f"None of {assertion.value} found",
                )
            
            case "min_count":
                inline = set(re.findall(r"\[(\d+)\]", answer))
                count = len(inline)
                passed = count >= assertion.value
                return AssertionResult(
                    assertion_name=assertion.name,
                    passed=passed,
                    score=min(count / assertion.value, 1.0),
                    actual_value=count,
                    message=f"Found {count} citations, need ≥ {assertion.value}",
                )
            
            case "max_value":
                passed = latency_ms <= assertion.value
                return AssertionResult(
                    assertion_name=assertion.name,
                    passed=passed,
                    score=1.0 if passed else max(0, 1 - (latency_ms - assertion.value) / assertion.value),
                    actual_value=latency_ms,
                    message=f"{latency_ms:.0f}ms {'✓' if passed else f'> limit {assertion.value}ms'}",
                )
            
            case "custom":
                if assertion.value == "all_inline_cite_ids_have_references":
                    inline = {int(n) for n in re.findall(r"\[(\d+)\]", answer)}
                    ref_ids = {r["id"] for r in references}
                    orphaned = inline - ref_ids
                    passed = len(orphaned) == 0
                    return AssertionResult(
                        assertion_name=assertion.name,
                        passed=passed,
                        score=1.0 if passed else 0.0,
                        actual_value=list(orphaned),
                        message=f"Orphaned citations: {orphaned}" if not passed else "All aligned",
                    )
                return AssertionResult(assertion.name, False, 0.0, None, f"Unknown custom check: {assertion.value}")
            
            case _:
                return AssertionResult(assertion.name, False, 0.0, None, f"Unknown check type: {assertion.check}")
    
    def aggregate(
        self,
        test_case: EvalTestCase,
        assertion_results: list[AssertionResult],
    ) -> dict:
        """Compute weighted aggregate score and overall pass/fail."""
        total_weight = sum(a.weight for a in test_case.assertions)
        
        weighted_score = sum(
            r.score * a.weight
            for r, a in zip(assertion_results, test_case.assertions)
        ) / total_weight if total_weight > 0 else 0.0
        
        # Zero-tolerance checks override weighted score
        zero_tolerance_failures = [
            r for r, a in zip(assertion_results, test_case.assertions)
            if a.zero_tolerance and not r.passed
        ]
        
        passed = weighted_score >= 0.8 and len(zero_tolerance_failures) == 0
        
        return {
            "test_id": test_case.id,
            "name": test_case.name,
            "difficulty": test_case.difficulty,
            "weighted_score": weighted_score,
            "passed": passed,
            "zero_tolerance_failures": [f.assertion_name for f in zero_tolerance_failures],
            "assertion_results": [
                {"name": r.assertion_name, "passed": r.passed, "score": r.score, "message": r.message}
                for r in assertion_results
            ],
        }
```

---

## Harness Runner

```python
import asyncio
from datetime import datetime

class EvalHarness:
    def __init__(self, pipeline, test_cases: list[EvalTestCase] = None):
        self.pipeline = pipeline
        self.test_cases = test_cases or NOOCYTE_TEST_CASES
        self.scorer = EvalScorer()
    
    async def run_single(self, test_case: EvalTestCase) -> dict:
        """Run one test case, return scored result."""
        start = time.perf_counter()
        
        try:
            output = await self.pipeline.process(test_case.input)
            latency_ms = (time.perf_counter() - start) * 1000
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            return {
                "test_id": test_case.id, "name": test_case.name,
                "passed": False, "weighted_score": 0.0,
                "error": str(e), "latency_ms": latency_ms,
            }
        
        assertion_results = self.scorer.score_output(test_case, output, latency_ms)
        result = self.scorer.aggregate(test_case, assertion_results)
        result["latency_ms"] = latency_ms
        return result
    
    async def run_all(self, concurrency: int = 3) -> dict:
        """Run all test cases with controlled concurrency."""
        semaphore = asyncio.Semaphore(concurrency)
        
        async def run_with_sem(tc):
            async with semaphore:
                return await self.run_single(tc)
        
        results = await asyncio.gather(
            *[run_with_sem(tc) for tc in self.test_cases],
            return_exceptions=False,
        )
        
        passed = sum(1 for r in results if r.get("passed", False))
        total = len(results)
        
        return {
            "run_at": datetime.utcnow().isoformat(),
            "summary": f"{passed}/{total} passed",
            "pass_rate": passed / total,
            "meets_launch_threshold": passed >= 7,  # Week 3 target
            "avg_latency_ms": sum(r.get("latency_ms", 0) for r in results) / total,
            "results": results,
            "failures": [r for r in results if not r.get("passed", False)],
        }
    
    def print_report(self, run_result: dict) -> None:
        """Print human-readable evaluation report."""
        print(f"\n{'='*60}")
        print(f"EVAL HARNESS REPORT — {run_result['run_at']}")
        print(f"{'='*60}")
        print(f"Result: {run_result['summary']} | Avg latency: {run_result['avg_latency_ms']:.0f}ms")
        print(f"Launch threshold (7/10): {'✅ MET' if run_result['meets_launch_threshold'] else '❌ NOT MET'}")
        print()
        
        for result in run_result["results"]:
            status = "✅" if result.get("passed") else "❌"
            print(f"{status} [{result['test_id']}] {result['name']}")
            print(f"   Score: {result.get('weighted_score', 0):.2f} | Latency: {result.get('latency_ms', 0):.0f}ms")
            
            if not result.get("passed"):
                for ar in result.get("assertion_results", []):
                    if not ar["passed"]:
                        print(f"   ↳ FAIL [{ar['name']}]: {ar['message']}")
        
        print(f"\nFailed test IDs: {[r['test_id'] for r in run_result['failures']]}")
```

---

## Running the Harness

```bash
# Full benchmark
python scripts/run_benchmark.py

# Single test case
python scripts/run_benchmark.py --test-id CDI-001

# Specific difficulty
python scripts/run_benchmark.py --difficulty hard

# Compare to baseline
python scripts/run_benchmark.py --compare baseline_2025_01_15.json
```

---

## Regression Tracking

Save results as JSON and compare over time:

```python
def detect_regressions(current: dict, baseline: dict) -> list[str]:
    """Find test cases that passed baseline but fail current."""
    baseline_passed = {r["test_id"] for r in baseline["results"] if r.get("passed")}
    current_passed = {r["test_id"] for r in current["results"] if r.get("passed")}
    
    regressions = baseline_passed - current_passed
    improvements = current_passed - baseline_passed
    
    if regressions:
        print(f"⚠️  REGRESSIONS: {regressions}")
    if improvements:
        print(f"✨ IMPROVEMENTS: {improvements}")
    
    return list(regressions)
```
