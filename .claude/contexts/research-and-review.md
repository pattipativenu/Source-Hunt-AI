# Research Mode Context

Activate this context when exploring options, evaluating libraries, or designing new features.

## Active Mode: Research

**Constraints in this mode:**
- Read before writing. Search official docs, GitHub issues, and recent benchmarks before proposing any solution.
- Use `skills/search-first/SKILL.md` as the research protocol.
- Document findings as an ADR using `agents/architect.md` template before writing any code.
- Check for known limitations before recommending a library.

**Research sources (in priority order):**
1. Official documentation and GitHub README
2. GitHub Issues and Discussions (reveals real-world problems)
3. Benchmark papers and leaderboards (BEIR, MTEB, RAGAS)
4. Recent blog posts from maintainers (< 12 months)

**Output of research mode:** A written recommendation with alternatives, trade-offs, and a "revisit when" trigger — not just "use X."

---

# Review Mode Context

Activate this context when reviewing a PR, code file, or architecture.

## Active Mode: Review

**Load automatically:**
- `agents/code-reviewer.md` (always)
- `agents/senior-python-engineer.md` (if Python)
- `agents/senior-ai-engineer.md` (if RAG/LLM code)
- `agents/security-reviewer.md` (if auth/input/external APIs)
- `agents/senior-medical-advisor.md` (if medical content output)

**Review order:**
1. Safety (medical constraints, security) — Critical failures end the review
2. Correctness (logic, error handling, edge cases)
3. Quality (naming, complexity, testability)
4. Performance (N+1, blocking I/O, missing cache)

**Output format:** Always use severity tiers. Always end with what's done well.
