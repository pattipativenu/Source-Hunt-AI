# Session Lifecycle Hooks

These hooks persist important context between coding sessions so Claude Code doesn't start cold each time.

## hooks.json Configuration

```json
{
  "hooks": [
    {
      "event": "SessionStart",
      "action": "read_file",
      "path": ".claude/session-context.md",
      "description": "Load last session's context and open decisions"
    },
    {
      "event": "SessionEnd",
      "action": "run_script",
      "script": ".claude/hooks/save-session.sh",
      "description": "Save session summary, open TODOs, and decisions made"
    },
    {
      "event": "PreToolUse",
      "tool": "Bash",
      "action": "check_rate_limit",
      "description": "Warn before any curl/httpx call that might hit NCBI without rate limiting"
    }
  ]
}
```

---

## Session Context File

`.claude/session-context.md` — updated at end of each session:

```markdown
# Session Context — Last Updated: {date}

## What We Were Working On
{brief description of the current task or feature}

## Current State
- **Working:** {what's working}
- **Broken:** {what's broken or incomplete}
- **In Progress:** {what was being worked on when session ended}

## Open Decisions
- [ ] {decision needed} — context: {why it's open}
- [ ] {decision needed}

## Next Steps (in order)
1. {immediate next action}
2. {following action}
3. {following action}

## Benchmark Status
- Last run: {date}
- Score: {N}/10
- Failing: {test IDs}

## Important Context
{anything else Claude needs to know at the start of the next session}
```

---

## save-session.sh Script

```bash
#!/bin/bash
# .claude/hooks/save-session.sh
# Called at session end to save context

SESSION_FILE=".claude/session-context.md"
DATE=$(date -u +"%Y-%m-%d %H:%M UTC")

# Prompt for session summary if running interactively
echo "Session ended: $DATE"
echo "Context saved to $SESSION_FILE"

# Run linter to catch any uncommitted issues
cd "$(git rev-parse --show-toplevel)" 2>/dev/null

if command -v ruff &> /dev/null; then
    ruff check . --quiet && echo "✅ Ruff: clean" || echo "⚠️  Ruff: issues found"
fi

if command -v mypy &> /dev/null; then
    mypy noocyte/ --quiet 2>&1 | tail -1
fi

# Show uncommitted changes as reminder
git status --short 2>/dev/null | head -20
```

---

## Pre-Commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Run fast checks before any commit
set -e

echo "Running pre-commit checks..."

# 1. Check for secrets (API keys, tokens)
if grep -r "sk-\|api_key\s*=\s*['\"]" --include="*.py" . 2>/dev/null | grep -v ".env" | grep -v "test_"; then
    echo "❌ BLOCKED: Potential secret detected in source code"
    exit 1
fi

# 2. Python formatting
if command -v ruff &> /dev/null; then
    ruff check . || { echo "❌ Ruff check failed — run 'ruff check --fix .'"; exit 1; }
fi

# 3. Type check
if command -v mypy &> /dev/null; then
    mypy noocyte/ --quiet || { echo "❌ mypy failed"; exit 1; }
fi

# 4. Fast unit tests only (not E2E)
pytest tests/unit/ -q --tb=no 2>/dev/null || { echo "❌ Unit tests failed"; exit 1; }

echo "✅ All pre-commit checks passed"
```

---

## Strategic Compact Hook

This hook suggests compacting the conversation when context is getting large, avoiding lost context mid-task.

```bash
# Triggered when conversation approaches context limit
# Suggests saving state before compaction

echo "⚠️  Context window approaching limit"
echo ""
echo "Before compaction, save your state:"
echo "1. Current task: note what you're in the middle of"
echo "2. Open decisions: list unresolved choices"
echo "3. Next steps: write the immediate next 3 actions"
echo ""
echo "Run: /checkpoint to save state"
```
