# /multi-plan

Decompose a complex feature or task into parallel workstreams with clear interfaces.

## Instructions

Given a feature description, produce a structured implementation plan that:

1. **Identifies dependencies** — what must be built before what
2. **Finds parallelism** — what can be built simultaneously
3. **Defines interfaces** — API contracts between components before coding starts
4. **Assigns specialists** — which agent type should handle each workstream

## Output Format

```
## Feature: [Name]

### Dependency Graph
[A] → [B] → [D]
[C] --------→

### Workstream 1: [Name] (no dependencies — start immediately)
Agent: senior-python-engineer
Deliverable: [concrete artifact]
Interface: [function signature / API schema]
Estimated complexity: [S/M/L]

### Workstream 2: [Name] (depends on Workstream 1 interface)
...

### Integration Points
- Workstream 1 ↔ Workstream 2: [exact interface]
- Shared types: [file path]

### Validation Criteria
- [ ] [Specific, testable criterion]
```

---

# /multi-execute

Execute a multi-workstream plan, coordinating between specialist agents.

## Instructions

1. Read the plan from `/multi-plan` output or provided context
2. For each workstream without dependencies, begin implementation
3. After each workstream completes, run its tests
4. Integrate only after all tests pass
5. Run integration tests last

## Execution Order Protocol

```
Phase 1: Foundation (interfaces + types)
  → Define shared data models
  → Create empty module stubs with correct signatures

Phase 2: Independent workstreams (parallel where possible)
  → Implement + test each in isolation

Phase 3: Integration
  → Wire workstreams together
  → Run integration tests

Phase 4: Verification
  → Run full test suite
  → Check against validation criteria from plan
```

## For Noocyte Specifically

Typical parallel workstreams:
- **Data layer** (Qdrant schema, Firestore migration) — no LLM dependency
- **PubMed client** (E-utilities wrapper) — independent
- **Query router** (intent classification) — depends on types only
- **WhatsApp handler** (webhook + formatter) — independent of RAG
- **Citation verifier** (NLI pipeline) — depends on RAG output schema

Build data models and interfaces first. Then all five workstreams can proceed in parallel.
