# /code-review

Perform a comprehensive code review of the specified file or PR diff.

Load: `agents/code-reviewer.md` + relevant language reviewer (python/typescript/etc.)

Produce output in severity format: 🔴 Critical → 🟠 Major → 🟡 Minor → 🔵 Note

Always end with: "Approved ✓ [list what's done well]" or "Changes Required [summary]"

---

# /tdd

Start a TDD cycle for the specified function or feature.

1. Define what the function must do (acceptance criteria)
2. Write the smallest possible failing test
3. Run it: confirm RED
4. Write minimum implementation to pass
5. Run: confirm GREEN
6. Refactor (clean without breaking)
7. Repeat

Load: `skills/tdd-workflow/SKILL.md` for patterns.

Output each step explicitly. Don't skip from RED to a complete implementation.

---

# /plan

Generate a structured implementation plan for the specified feature.

Load: `agents/planner.md`

Produce:
- Dependency graph
- Phased task list (each task: agent, inputs, outputs, acceptance criteria, size estimate)
- Execution order summary
- Open questions that block implementation

---

# /e2e

Generate or run end-to-end tests for the specified user flow.

For Noocyte: test the complete WhatsApp query → RAG pipeline → WhatsApp delivery flow.

Steps:
1. Define the user scenario in plain English
2. Identify the system boundaries to test (webhook → Pub/Sub → worker → WhatsApp API)
3. Write integration test using mocked external APIs
4. Confirm the test covers: happy path + empty results + pipeline error + WhatsApp delivery failure

---

# /security-check

Run security review against the specified component or PR.

Load: `agents/security-reviewer.md` + `skills/security-review/SKILL.md`

Check order:
1. Input validation
2. Authentication/signature verification
3. Secret management
4. Injection vectors
5. Rate limiting
6. Prompt injection (if AI component)
7. PII in logs
8. Dependency vulnerabilities (`safety check`)

Output: sorted by severity, with specific line references and fix suggestions.

---

# /benchmark

Run the 10-query OpenEvidence benchmark against the current pipeline.

Load: `agents/harness-optimizer.md`

Steps:
1. Run all 10 queries through the live pipeline
2. Score each on: citation count, alignment, required terms, forbidden phrases, latency
3. Report: X/10 pass, failing queries with specific failure reasons
4. Compare to previous benchmark if available
5. Suggest top-3 improvements based on failure patterns

Target: ≥ 7/10 for Week 3, ≥ 9/10 for production.
