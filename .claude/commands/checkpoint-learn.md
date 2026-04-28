# /checkpoint

Save the current session state before a long task, context compaction, or end of session.

## Instructions

Write a checkpoint to `.claude/session-context.md` with:

```markdown
# Session Context — {current datetime}

## Task in Progress
{what are we in the middle of right now}

## Current State
- Working: {what is complete and verified}
- Incomplete: {what was started but not finished}
- Blocked: {anything blocking progress}

## Open Decisions
{list any unresolved architecture or implementation choices}

## Immediate Next Steps
1. {first thing to do when resuming}
2. {second thing}
3. {third thing}

## Benchmark Status
- Score: {N}/10
- Failing: {test IDs if benchmark was run}

## Key Context
{anything important Claude needs to know at session resume that isn't obvious from the code}
```

Always write this before any major context compaction.

---

# /learn

Extract patterns and insights from the current session to preserve as reusable knowledge.

## Instructions

Review the current session and identify:

1. **Problems solved** — non-obvious solutions worth remembering
2. **Mistakes made and corrected** — patterns to avoid in future
3. **Decisions made** — architecture choices and their rationale
4. **Effective patterns** — approaches that worked particularly well

Format as:

```markdown
## Session Learning — {date}

### Solutions Worth Remembering
- **[Problem]:** [Solution and why it works]

### Mistakes to Avoid  
- **[Mistake]:** [Why it's wrong and what to do instead]

### Decisions Made
- **[Decision]:** [Rationale and trade-offs]

### Effective Patterns
- **[Pattern]:** [When to apply it]
```

Append to `.claude/learnings.md` (create if it doesn't exist).
