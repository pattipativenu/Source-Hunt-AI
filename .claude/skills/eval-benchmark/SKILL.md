---
name: eval-benchmark
description: >
  Run, interpret, and act on the Noocyte AI benchmark suite against the 10
  OpenEvidence gold-standard queries. Use when measuring pipeline quality,
  validating sprint milestone gates, comparing prompt or model changes, or
  diagnosing why specific queries are failing. Covers scoring rubric,
  failure mode classification, and improvement recommendations.
argument-hint: "<benchmark file path> [--target-score N]"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write
---

# Eval Benchmark

## Purpose

You cannot improve what you cannot measure. The benchmark suite is the single most important quality signal for Noocyte AI. It tells you, objectively, whether the pipeline is getting better or worse after each change.

The 10 OpenEvidence benchmark queries represent the gold standard for clinical decision support quality. Every sprint milestone is defined in terms of how many of these 10 queries pass.

---

## The 10 Benchmark Queries

These are the exact queries from the OpenEvidence benchmark, categorized by difficulty:

```python
# tests/benchmark/openevidence_10.json
BENCHMARK_QUERIES = [
    # EASY (target: pass by Week 1)
    {
        "id": "BQ-01",
        "query": "First-line treatment for Clostridioides difficile infection (CDI)?",
        "difficulty": "easy",
        "key_elements": ["fidaxomicin", "vancomycin", "IDSA/SHEA 2021", "recurrence rate"],
        "india_specific": False,
    },
    {
        "id": "BQ-02",
        "query": "Anticoagulation choice in AF with CKD stage 3b?",
        "difficulty": "easy",
        "key_elements": ["apixaban", "eGFR", "dose reduction", "ARISTOTLE trial"],
        "india_specific": False,
    },
    {
        "id": "BQ-03",
        "query": "HbA1c target for elderly T2DM patients?",
        "difficulty": "easy",
        "key_elements": ["7-8%", "ADA 2024", "hypoglycemia risk", "frailty"],
        "india_specific": False,
    },
    
    # MEDIUM (target: pass by Week 2)
    {
        "id": "BQ-04",
        "query": "SGLT2 inhibitor choice in heart failure with reduced ejection fraction?",
        "difficulty": "medium",
        "key_elements": ["empagliflozin", "dapagliflozin", "EMPEROR-Reduced", "DAPA-HF", "NNT"],
        "india_specific": False,
    },
    {
        "id": "BQ-05",
        "query": "Statin intensity for primary prevention in 55-year-old with 12% 10-year CVD risk?",
        "difficulty": "medium",
        "key_elements": ["moderate-intensity", "ACC/AHA 2019", "ASCVD risk", "shared decision making"],
        "india_specific": False,
    },
    {
        "id": "BQ-06",
        "query": "Duration of dual antiplatelet therapy after drug-eluting stent for stable CAD?",
        "difficulty": "medium",
        "key_elements": ["6 months", "ESC 2023", "bleeding risk", "DAPT score"],
        "india_specific": False,
    },
    
    # HARD (target: pass by Week 3)
    {
        "id": "BQ-07",
        "query": "Treatment of MDR-TB in India — what does ICMR recommend?",
        "difficulty": "hard",
        "key_elements": ["BPaL regimen", "bedaquiline", "ICMR", "PMDT", "pretomanid"],
        "india_specific": True,
    },
    {
        "id": "BQ-08",
        "query": "Apixaban vs rivaroxaban in AF with moderate CKD — which is preferred?",
        "difficulty": "hard",
        "key_elements": ["apixaban preferred", "bleeding risk", "ARISTOTLE subgroup", "eGFR 30-50"],
        "india_specific": False,
    },
    {
        "id": "BQ-09",
        "query": "Fidaxomicin vs vancomycin for recurrent CDI — what does the evidence show?",
        "difficulty": "hard",
        "key_elements": ["fidaxomicin preferred", "16% vs 25%", "MODIFY I/II", "fidaxomicin cost"],
        "india_specific": False,
    },
    {
        "id": "BQ-10",
        "query": "Dolo 650 for fever — what is the evidence and appropriate dosing?",
        "difficulty": "hard",
        "key_elements": ["paracetamol", "650mg", "4g/day max", "Indian context", "brand resolution"],
        "india_specific": True,
    },
]
```

---

## The Scoring Rubric

Each query is scored on 5 dimensions (0 or 1 each), maximum 5 points per query:

```python
def score_response(response: dict, benchmark_query: dict) -> dict:
    """
    Score a Noocyte AI response against the benchmark rubric.
    
    Returns a score dict with dimension scores and total.
    """
    scores = {}
    
    # Dimension 1: Key Elements Present (0 or 1)
    # Does the answer contain the key clinical elements?
    key_elements = benchmark_query["key_elements"]
    answer_lower = response["answer"].lower()
    elements_found = sum(1 for el in key_elements if el.lower() in answer_lower)
    scores["key_elements"] = 1 if elements_found >= len(key_elements) * 0.75 else 0
    
    # Dimension 2: Citation Quality (0 or 1)
    # Does the answer have ≥ 2 inline citations with DOIs?
    citations = response.get("citations", [])
    has_dois = sum(1 for c in citations if c.get("doi"))
    scores["citation_quality"] = 1 if has_dois >= 2 else 0
    
    # Dimension 3: No Prescriptive Language (0 or 1)
    # Does the answer avoid prescriptive language?
    prescriptive_terms = ["prescribe", "administer", "give the patient", "start on", "you should give"]
    has_prescriptive = any(term in answer_lower for term in prescriptive_terms)
    scores["no_prescriptive_language"] = 0 if has_prescriptive else 1
    
    # Dimension 4: India Context (0 or 1) — only for india_specific queries
    if benchmark_query["india_specific"]:
        india_terms = ["icmr", "india", "indian", "pmdt", "₹", "rupee", "cdsco"]
        has_india_context = any(term in answer_lower for term in india_terms)
        scores["india_context"] = 1 if has_india_context else 0
    else:
        scores["india_context"] = 1  # N/A — auto-pass for non-India queries
    
    # Dimension 5: Confidence Level Present (0 or 1)
    scores["confidence_level"] = 1 if response.get("confidence_level") in ["HIGH", "MEDIUM", "LOW"] else 0
    
    total = sum(scores.values())
    passed = total >= 4  # Pass threshold: 4/5 dimensions
    
    return {
        "query_id": benchmark_query["id"],
        "total_score": total,
        "passed": passed,
        "dimension_scores": scores,
        "failure_modes": [k for k, v in scores.items() if v == 0],
    }
```

---

## Running the Benchmark

```bash
# Run the full benchmark
python3 scripts/run_benchmark.py \
  --queries tests/benchmark/openevidence_10.json \
  --output results/benchmark_$(date +%Y%m%d_%H%M%S).json

# Run a single query for debugging
python3 scripts/run_benchmark.py \
  --query-id BQ-07 \
  --verbose

# Run only India-specific queries
python3 scripts/run_benchmark.py \
  --filter india_specific=true
```

```python
# scripts/run_benchmark.py
import asyncio
import json
from datetime import datetime
from pathlib import Path

async def run_benchmark(queries_file: str, output_file: str = None) -> dict:
    """Run the full benchmark suite and produce a report."""
    
    with open(queries_file) as f:
        queries = json.load(f)
    
    results = []
    
    for query in queries:
        print(f"Running {query['id']}: {query['query'][:60]}...")
        
        # Run through the full Noocyte AI pipeline
        response = await noocyte_pipeline(query["query"])
        
        # Score the response
        score = score_response(response, query)
        results.append(score)
        
        status = "✅ PASS" if score["passed"] else "❌ FAIL"
        print(f"  {status} ({score['total_score']}/5) | Failures: {score['failure_modes']}")
    
    # Aggregate results
    passing = sum(1 for r in results if r["passed"])
    total = len(results)
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "score": f"{passing}/{total}",
        "passing_count": passing,
        "total_count": total,
        "pass_rate": passing / total,
        "results": results,
        "failure_analysis": analyze_failure_modes(results),
        "sprint_gate": check_sprint_gate(passing),
    }
    
    if output_file:
        with open(output_file, "w") as f:
            json.dump(report, f, indent=2)
    
    return report

def check_sprint_gate(passing_count: int) -> str:
    """Map benchmark score to sprint milestone."""
    if passing_count >= 9:
        return "WEEK_4_GATE_PASSED — Ready for soft launch"
    elif passing_count >= 7:
        return "WEEK_3_GATE_PASSED — Ready for doctor testing"
    elif passing_count >= 5:
        return "WEEK_2_GATE_PASSED — Core pipeline working"
    elif passing_count >= 4:
        return "WEEK_1_GATE_PASSED — Basic retrieval working"
    else:
        return "BELOW_WEEK_1_GATE — Pipeline needs significant work"
```

---

## Interpreting Results

### Sprint Milestone Gates

| Score | Gate | Meaning |
|-------|------|---------|
| 9-10/10 | Week 4 | Ready for soft launch with real doctors |
| 7-8/10 | Week 3 | Ready for doctor testing and feedback |
| 5-6/10 | Week 2 | Core pipeline working, India context needs work |
| 4/10 | Week 1 | Basic retrieval working |
| < 4/10 | Below Week 1 | Fundamental pipeline issue |

### Common Failure Patterns and Fixes

```python
FAILURE_MODE_FIXES = {
    "key_elements": {
        "diagnosis": "The right chunks are not being retrieved or the answer is not synthesizing them",
        "quick_check": "Print the top 5 chunks for this query — are the key elements present in the chunks?",
        "fix_if_chunks_missing": "Expand the brand dictionary, improve PICO extraction, or add the missing source to Qdrant",
        "fix_if_chunks_present": "Improve the context assembly or the generation prompt",
    },
    "citation_quality": {
        "diagnosis": "Gemini is not generating citations, or DOIs are missing",
        "quick_check": "Check the response JSON — are citations present? Do they have DOIs?",
        "fix": "Update the system prompt to require DOIs. Check that source chunks include DOI metadata.",
    },
    "no_prescriptive_language": {
        "diagnosis": "The system prompt constraint is not being followed",
        "quick_check": "Search the response for 'prescribe', 'administer', 'give the patient'",
        "fix": "Add the prescriptive language constraint to Layer 2 of the system prompt. Add a few-shot example that demonstrates the correct phrasing.",
    },
    "india_context": {
        "diagnosis": "ICMR sources not in Qdrant, or India context injection not working",
        "quick_check": "Check if ICMR guidelines are ingested. Check if prefer_icmr flag is set for this query.",
        "fix": "Ingest ICMR guidelines for this condition. Verify the india_context_injector is running.",
    },
}
```

---

## Tracking Progress Over Time

```bash
# Compare two benchmark runs
python3 scripts/compare_benchmarks.py \
  results/benchmark_20260115_120000.json \
  results/benchmark_20260116_140000.json

# Output:
# Score: 5/10 → 7/10 (+2)
# New passes: BQ-07 (MDR-TB), BQ-10 (Dolo 650)
# New failures: none
# Improvement: india_context dimension improved from 0% to 100%
```

---

*If you're not measuring it, you're not improving it. Run the benchmark after every significant change.*
