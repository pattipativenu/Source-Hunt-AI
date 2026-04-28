# AGENTS.md — Sub-Agent Delegation Guide

When a task requires specialist knowledge, delegate to the appropriate sub-agent by loading their instructions from the `agents/` directory. This file maps task types to the correct agent.

## When to Delegate

Delegate when:
- The task requires deep domain expertise (RAG pipelines, medical content, security)
- The task has well-defined inputs, outputs, and acceptance criteria
- You want a structured review rather than ad-hoc comments
- You're making an irreversible decision (architecture, database schema, API contract)

Do NOT delegate when:
- The task is simple enough to complete directly in 5 minutes
- You need the context of the current conversation to answer
- The delegation overhead exceeds the task itself

---

## Agent Directory

### 🗺️ Planning & Architecture

**`agents/planner.md`**
Use for: Feature planning, task decomposition, dependency mapping, estimation
Input: Feature description or user story
Output: Phased task list with dependency graph, acceptance criteria, size estimates, and open questions
When: Before starting any multi-file feature or when requirements are vague

**`agents/architect.md`**
Use for: Technology decisions, architecture design, trade-off analysis, ADR creation
Input: Technical problem or design question
Output: Architecture Decision Record (ADR) with alternatives, consequences, costs at scale
When: Before choosing a library, database, or service pattern; when making decisions that are hard to reverse

---

### 🐍 Python Engineering

**`agents/senior-python-engineer.md`**
Use for: Python code review, async correctness, type safety, error handling, logging, configuration
Input: Python file(s) or PR diff
Output: Categorised review (🔴 Critical, 🟠 Major, 🟡 Minor, 🔵 Note) with specific fixes
When: After writing any new Python module; before any merge

**`agents/build-error-resolver.md`**
Use for: Python import errors, dependency conflicts, async event loop errors, GCP auth failures, Qdrant connection errors
Input: Full error message + stack trace
Output: Root cause identification + fix + verification command
When: Stuck on a build or runtime error for more than 10 minutes

**`agents/typescript-reviewer.md`**
Use for: TypeScript/JavaScript code review, type safety, async/await patterns, Zod validation
Input: TypeScript file(s) or PR diff
Output: Structured review with severity levels
When: Reviewing any TypeScript API, webhook handler, or frontend code

---

### 🤖 AI / RAG Pipeline

**`agents/senior-ai-engineer.md`**
Use for: RAG pipeline review, embedding architecture, retrieval quality, reranking, generation config, citation integrity, RAGAS evaluation
Input: RAG pipeline code or architecture description
Output: Detailed review across: embedding, retrieval, reranking, generation, verification — each with specific code examples
When: After any change to the retrieval pipeline, prompt, or generation config; always before running the benchmark

---

### 🏥 Medical Domain

**`agents/senior-medical-advisor.md`**
Use for: Medical content review, prescriptive language detection, drug safety flags, evidence hierarchy validation, citation accuracy, emergency detection
Input: Generated medical response or system prompt
Output: SAFETY/EVIDENCE/CONCERNS/RECOMMENDATION assessment
When: Reviewing system prompts; after any change to response formatting or citation templates; when adding new medical content categories

---

### 🔒 Security

**`agents/security-reviewer.md`**
Use for: Security audit, input validation, webhook signature verification, prompt injection defence, secret management, rate limiting design, PII handling
Input: Code component (webhook handler, API endpoint, query pipeline)
Output: Severity-ordered security findings with specific CWE references and fixes
When: Before any PR involving user input, authentication, external API calls, or LLM integration

---

### 🗄️ Data & Databases

**`agents/database-reviewer.md`**
Use for: Qdrant collection design, payload index creation, Redis TTL policies, Firestore query patterns, PostgreSQL optimisation
Input: Database schema, query patterns, or migration plan
Output: Issues with specific fixes for each database type
When: Before creating a new Qdrant collection; when adding database queries; when designing data migration

---

### 📊 Evaluation & Quality

**`agents/harness-optimizer.md`**
Use for: Benchmark design, quality gate calibration, RAGAS metric evaluation, test case analysis, failure pattern identification
Input: Current benchmark results + pipeline description
Output: Failure analysis, root cause mapping, improvement recommendations
When: After running the 10-query benchmark; when benchmark scores plateau; when designing quality gates for new features

---

### 🔄 Code Quality

**`agents/code-reviewer.md`**
Use for: General code quality review — correctness, error handling, API design, performance, test coverage
Input: Code file(s) or PR diff
Output: Structured review using 🔴/🟠/🟡/🔵 severity
When: For code not covered by language-specific reviewers; for architecture-level review

---

## Delegation Pattern

```
1. Identify the task type from the table above
2. Load the agent: "Read agents/[agent-name].md and apply its review criteria to:"
3. Provide specific input
4. Review agent output — you remain responsible for final decisions
```

Example delegation:
```
"Load agents/senior-python-engineer.md and review noocyte/core/query_router.py"
"Load agents/security-reviewer.md and audit the webhook handler in api/routes/webhook.py"  
"Load agents/harness-optimizer.md — the benchmark shows 5/10 pass, citation_alignment failures on Q4 and Q7. Identify root causes and recommend fixes."
```

---

## Multi-Agent Workflows

For complex features, chain agents in sequence:

```
/plan → planner produces task list
  ↓
/tdd → implement each task test-first
  ↓
/python-review → senior-python-engineer reviews implementation
  ↓
/security-check → security-reviewer audits if touching auth/input/LLM
  ↓
/benchmark → harness-optimizer validates quality gates pass
  ↓
Merge
```
