# Pre-Commit Hook — Noocyte AI

This hook runs automatically before every `git commit`. It enforces the always-on rules and prompt writing rules before any code reaches the repository.

**If this hook fails, the commit is blocked.** Fix the issues it reports, then commit again.

---

## What This Hook Checks

### Check 1: Prescriptive Language Scan (CRITICAL)

Scans all modified Python files and prompt files for prohibited prescriptive phrases.

```bash
#!/bin/bash
# .git/hooks/pre-commit (excerpt)

PROHIBITED_PHRASES=(
  "prescribe"
  "administer"
  "give the patient"
  "give your patient"
  "start the patient on"
  "you should give"
  "I recommend giving"
)

echo "🔍 Scanning for prescriptive language..."
FOUND=0
for phrase in "${PROHIBITED_PHRASES[@]}"; do
  matches=$(git diff --cached --name-only | xargs grep -l -i "$phrase" 2>/dev/null)
  if [ -n "$matches" ]; then
    echo "❌ CRITICAL: Prescriptive phrase '$phrase' found in: $matches"
    FOUND=1
  fi
done

if [ $FOUND -eq 1 ]; then
  echo ""
  echo "Fix: Replace prescriptive language with evidence-based language."
  echo "See: .claude/rules/always-on.md Rule 1"
  exit 1
fi
echo "✅ No prescriptive language found."
```

### Check 2: PII Pattern Scan (CRITICAL)

Scans all modified files for hardcoded PII patterns (test data that should never be committed).

```bash
PII_PATTERNS=(
  "[0-9]{4}[[:space:]][0-9]{4}[[:space:]][0-9]{4}"  # Aadhaar
  "\+91[[:space:]-]?[6-9][0-9]{9}"                   # Indian phone
  "[A-Z]{5}[0-9]{4}[A-Z]"                            # PAN card
)

echo "🔍 Scanning for hardcoded PII..."
FOUND=0
for pattern in "${PII_PATTERNS[@]}"; do
  matches=$(git diff --cached --name-only | xargs grep -lE "$pattern" 2>/dev/null)
  if [ -n "$matches" ]; then
    echo "❌ CRITICAL: Potential PII pattern found in: $matches"
    FOUND=1
  fi
done

if [ $FOUND -eq 1 ]; then
  echo ""
  echo "Fix: Remove real PII from test data. Use synthetic data instead."
  echo "See: .claude/rules/always-on.md Rule 4"
  exit 1
fi
echo "✅ No hardcoded PII found."
```

### Check 3: Temperature Check (WARNING)

Scans for Gemini API calls with temperature > 0.1.

```bash
echo "🔍 Checking Gemini temperature settings..."
high_temp=$(git diff --cached --name-only | xargs grep -n "temperature=[0-9]*\.[2-9]" 2>/dev/null)
if [ -n "$high_temp" ]; then
  echo "⚠️  WARNING: High temperature setting found:"
  echo "$high_temp"
  echo ""
  echo "Medical generation requires temperature ≤ 0.1"
  echo "See: .claude/rules/always-on.md Rule 5"
  # Warning only — does not block commit
fi
```

### Check 4: Prompt Size Check (WARNING)

Checks if any modified prompt files exceed 800 tokens (approximated as 3200 characters).

```bash
echo "🔍 Checking prompt file sizes..."
PROMPT_FILES=$(git diff --cached --name-only | grep -E "\.(xml|md|txt)$" | grep -i "prompt")
for f in $PROMPT_FILES; do
  chars=$(wc -c < "$f")
  if [ "$chars" -gt 3200 ]; then
    echo "⚠️  WARNING: Prompt file $f may exceed 800 tokens ($chars chars)"
    echo "See: .claude/rules/prompt-writing.md Rule P-3"
  fi
done
```

### Check 5: Benchmark Test (WARNING on CI, CRITICAL on main branch)

```bash
echo "🔍 Running benchmark smoke test..."
BRANCH=$(git branch --show-current)
if [ "$BRANCH" = "main" ]; then
  python3 scripts/run_benchmark.py --quick --min-pass 7
  if [ $? -ne 0 ]; then
    echo "❌ CRITICAL: Benchmark score below 7/10 on main branch"
    exit 1
  fi
else
  echo "ℹ️  Skipping full benchmark on feature branch (run manually)"
fi
```

---

## Installing This Hook

```bash
# From the repository root:
cp .claude/hooks/pre-commit-script.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

Or use the setup script:

```bash
python3 scripts/setup_hooks.py
```

---

## Bypassing the Hook (Emergency Only)

If you must bypass the hook in an emergency:

```bash
git commit --no-verify -m "emergency: [reason]"
```

**This must be followed immediately by a follow-up commit that fixes the issue.** Bypassing the hook and not fixing the issue is a policy violation.

---

## The Session-Start Hook

In addition to the pre-commit hook, a session-start hook runs when Claude Code opens the project. It:

1. Reads `.claude/rules/always-on.md` and loads the rules into context
2. Reads `.claude/CLAUDE.md` to understand the current sprint milestone
3. Checks if any benchmark tests have been run in the last 24 hours
4. Reminds the developer of the current sprint gate target

```javascript
// .claude/hooks/session-start.js
module.exports = async function sessionStart({ claude }) {
  // Load always-on rules
  const rules = await claude.readFile('.claude/rules/always-on.md');
  await claude.remember('always_on_rules', rules);
  
  // Load current sprint status
  const claudeMd = await claude.readFile('.claude/CLAUDE.md');
  const sprintWeek = extractCurrentSprintWeek(claudeMd);
  
  // Remind developer of sprint gate
  const gates = {
    1: "Week 1 gate: 4/10 benchmark queries passing",
    2: "Week 2 gate: 5/10 benchmark queries + WhatsApp round-trip < 10s",
    3: "Week 3 gate: 7/10 benchmark queries passing",
    4: "Week 4 gate: 9/10 benchmark queries + Meta Business Verification",
  };
  
  await claude.notify(`📋 Sprint Week ${sprintWeek}: ${gates[sprintWeek]}`);
};
```

---

*Hooks are the safety net. They catch mistakes before they become problems.*
