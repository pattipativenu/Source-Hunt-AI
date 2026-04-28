---
name: autonomous-loop
description: >
  Run Noocyte AI development tasks in an autonomous generate-verify-correct loop
  without requiring human intervention at each step. Use when executing multi-step
  tasks like ingesting a new data source, running the benchmark suite, or
  iteratively improving RAG pipeline quality. Implements the
  Generate → Verify → Correct → Repeat pattern with automatic stopping conditions.
argument-hint: "<task description and stopping condition>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write, Edit
---

# Autonomous Loop

## Purpose

Most development tasks in Noocyte AI are iterative: write code → run tests → fix failures → run tests again. This skill formalizes that loop so it can run autonomously, with clear stopping conditions, maximum iteration limits, and automatic escalation when the loop cannot self-resolve.

This is the skill that enables Claude Code to work like a senior engineer — not just writing code, but running it, seeing what breaks, fixing it, and continuing until the task is done.

---

## The Core Loop Pattern

```python
# The autonomous loop in pseudocode
async def autonomous_loop(
    task: str,
    stopping_condition: Callable[[], bool],
    max_iterations: int = 10,
    escalate_after: int = 3,  # Escalate to human after N consecutive failures
) -> LoopResult:
    
    iteration = 0
    consecutive_failures = 0
    history = []
    
    while iteration < max_iterations:
        iteration += 1
        
        # 1. GENERATE: Execute the current task step
        result = await execute_step(task, history)
        history.append(result)
        
        # 2. VERIFY: Check if the result meets the stopping condition
        if stopping_condition():
            return LoopResult(success=True, iterations=iteration, history=history)
        
        # 3. ASSESS: Did we make progress?
        if result.is_worse_than_previous(history):
            consecutive_failures += 1
        else:
            consecutive_failures = 0
        
        # 4. ESCALATE: If stuck, ask for help
        if consecutive_failures >= escalate_after:
            return LoopResult(
                success=False,
                reason="Stuck after {consecutive_failures} consecutive failures",
                last_error=result.error,
                suggested_action=result.diagnosis,
                iterations=iteration,
                history=history,
            )
        
        # 5. CORRECT: Apply the fix and continue
        task = await generate_correction(task, result.error, history)
    
    return LoopResult(
        success=False,
        reason=f"Max iterations ({max_iterations}) reached",
        iterations=iteration,
        history=history,
    )
```

---

## Use Case 1: Benchmark Improvement Loop

The most important autonomous loop for Noocyte AI. Run this when the benchmark score is below the week's target.

```bash
# Trigger: benchmark score is 5/10, target is 7/10
# Loop: improve RAG pipeline until 7/10 or max 5 iterations

python scripts/autonomous_benchmark_loop.py \
  --target-score 7 \
  --max-iterations 5 \
  --queries tests/benchmark/openevidence_10.json
```

```python
# scripts/autonomous_benchmark_loop.py
async def benchmark_improvement_loop(target_score: int, max_iterations: int):
    """
    Autonomously improve RAG pipeline until benchmark target is met.
    
    Loop strategy:
    1. Run benchmark → get score and failure analysis
    2. Identify the most common failure mode
    3. Apply the corresponding fix
    4. Re-run benchmark
    5. Repeat until target or max iterations
    """
    
    FAILURE_MODE_FIXES = {
        "no_chunks_retrieved": "increase_qdrant_top_k",
        "wrong_source_priority": "boost_icmr_in_context_assembly",
        "citation_hallucinated": "lower_nli_threshold_or_add_crossref_check",
        "prescriptive_language": "update_system_prompt_constraints",
        "brand_not_resolved": "expand_indian_brand_dictionary",
        "query_misunderstood": "improve_pico_extraction_prompt",
    }
    
    for iteration in range(max_iterations):
        # Step 1: Run benchmark
        results = await run_benchmark(queries_file)
        score = results.passing_count
        
        print(f"Iteration {iteration + 1}: Score {score}/{len(results.queries)}")
        
        # Step 2: Check stopping condition
        if score >= target_score:
            print(f"✅ Target reached: {score}/{len(results.queries)}")
            return results
        
        # Step 3: Analyze failures
        failures = [r for r in results.queries if not r.passed]
        failure_modes = analyze_failure_modes(failures)
        top_failure = max(failure_modes, key=failure_modes.get)
        
        print(f"Top failure mode: {top_failure} ({failure_modes[top_failure]} queries)")
        
        # Step 4: Apply fix
        fix = FAILURE_MODE_FIXES.get(top_failure)
        if fix:
            await apply_fix(fix)
            print(f"Applied fix: {fix}")
        else:
            print(f"⚠️ Unknown failure mode: {top_failure} — escalating to human")
            break
    
    print(f"❌ Max iterations reached. Final score: {score}/{len(results.queries)}")
    return results
```

---

## Use Case 2: TDD Autonomous Loop

Write a test → run it (it fails) → write code to make it pass → run it again → repeat.

```bash
# Trigger: implement a new function using TDD
# Loop: write tests first, then implement until all tests pass

python scripts/tdd_loop.py \
  --function "resolve_brand_to_inn" \
  --test-file "tests/unit/test_indian_context_resolver.py" \
  --max-iterations 5
```

```python
# The TDD autonomous loop
async def tdd_loop(function_name: str, test_file: str, max_iterations: int = 5):
    """
    Red-Green-Refactor loop:
    1. Write tests (RED — they should fail)
    2. Write minimum code to pass (GREEN)
    3. Refactor (REFACTOR)
    4. Repeat for edge cases
    """
    
    for iteration in range(max_iterations):
        # Run tests
        result = subprocess.run(
            ["pytest", test_file, "-v", "--tb=short"],
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print(f"✅ All tests passing after {iteration + 1} iterations")
            return True
        
        # Parse failures
        failures = parse_pytest_output(result.stdout)
        print(f"Iteration {iteration + 1}: {len(failures)} tests failing")
        
        # Generate fix for the first failing test
        fix = await generate_fix(failures[0], function_name)
        apply_fix(fix)
    
    print(f"❌ Could not make all tests pass in {max_iterations} iterations")
    return False
```

---

## Use Case 3: Data Ingestion Loop

Ingest a new data source (e.g., new ICMR guidelines) with automatic quality verification.

```bash
# Trigger: new ICMR PDF needs to be ingested
# Loop: ingest → verify chunk quality → fix parsing → repeat

python scripts/ingest_loop.py \
  --source "data/icmr/icmr_tb_guidelines_2024.pdf" \
  --min-chunk-quality 0.8 \
  --max-iterations 3
```

---

## Stopping Conditions Reference

Define these clearly before starting any autonomous loop:

| Loop Type | Stopping Condition | Max Iterations |
|-----------|-------------------|----------------|
| Benchmark improvement | Score ≥ target (e.g., 7/10) | 5 |
| TDD loop | All tests passing | 5 |
| Build fix | `pytest` exit code 0 | 3 |
| Data ingest | Chunk quality ≥ 0.8 | 3 |
| Citation fix | All DOIs resolve | 3 |
| Type checking | `mypy --strict` exit code 0 | 3 |

---

## Escalation Protocol

When the loop cannot self-resolve, it escalates with a structured report:

```
AUTONOMOUS LOOP ESCALATION REPORT
Loop: benchmark-improvement
Iterations completed: 3/5
Final score: 5/10 (target: 7/10)

STUCK ON: citation_hallucinated (3 queries failing)

WHAT WAS TRIED:
  Iteration 1: Lowered NLI threshold from 0.7 to 0.6 → Score: 5/10 (no change)
  Iteration 2: Added CrossRef DOI validation → Score: 5/10 (no change)
  Iteration 3: Updated system prompt citation constraint → Score: 5/10 (no change)

ROOT CAUSE HYPOTHESIS:
  The NLI model (MedNLI) may not be loaded correctly — all NLI scores are 0.0.
  This means citation verification is not actually running.

RECOMMENDED HUMAN ACTION:
  1. Check RERANKER_SERVICE_URL in .env — NLI model may not be running
  2. Run: curl http://localhost:8084/health to verify NLI service
  3. If down: docker-compose up nli-service

RELEVANT LOGS:
  [ERROR] 2026-01-15 14:23:11 | nli_verifier | Connection refused: localhost:8084
```

---

## What NOT to Do

```python
# ❌ Infinite loop without stopping condition
while True:
    result = await run_benchmark()
    if result.score < target:
        await apply_random_fix()  # No systematic approach

# ❌ Swallowing errors in the loop
try:
    result = await execute_step(task)
except Exception:
    pass  # Silent failure — loop continues with bad state

# ❌ Not tracking history — can't diagnose why loop is stuck
result = await execute_step(task)
# No history → can't tell if we're making progress or going in circles

# ✅ Always track history, always have a stopping condition, always escalate
result = await autonomous_loop(
    task=task,
    stopping_condition=lambda: benchmark_score() >= 7,
    max_iterations=5,
    escalate_after=3,
)
```

---

*Autonomy without stopping conditions is chaos. Stopping conditions without autonomy is manual work.*
