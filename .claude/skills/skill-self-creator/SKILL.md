---
name: skill-self-creator
description: >
  Automatically detect when a required skill is missing and create a new,
  well-structured SKILL.md file for it. Use when you encounter a task that
  has no matching skill, when an existing skill is incomplete, or when a
  new domain of knowledge needs to be codified for the Noocyte AI project.
  Implements the "superpowers" pattern: if no skill exists, create one.
argument-hint: "<skill name> <description of what it should cover>"
disable-model-invocation: false
context: fork
allowed-tools: Bash, Read, Write, Edit
---

# Skill Self-Creator

## Purpose

A skill library is only as good as its coverage. When Claude Code encounters a task it has no skill for, it should not proceed with guesswork — it should create a new skill first, codifying the correct approach, then use that skill to complete the task.

This skill implements the **"if no skill exists, create one"** pattern. It is the meta-skill that keeps the Noocyte AI skill library growing and self-improving.

---

## When to Trigger This Skill

Trigger this skill automatically when:
1. You are about to do something and realize there is no skill covering it
2. You have completed a task and discovered important patterns that should be captured
3. An existing skill is missing a critical section (e.g., no testing examples)
4. A new external service or API is being integrated (e.g., a new data source)
5. A recurring mistake has been made that should be documented as a "What NOT to Do"

---

## The Skill Creation Protocol

### Step 1: Check if a Skill Already Exists

```bash
# Before creating a new skill, always check if one exists
ls .claude/skills/

# Also check if the topic is covered in an existing skill
grep -r "keyword" .claude/skills/ --include="*.md" -l
```

### Step 2: Define the Skill's Scope

Answer these four questions before writing a single line:

1. **What problem does this skill solve?** (1 sentence)
2. **When should it be triggered?** (specific conditions, not vague)
3. **What does a developer need to know to use it correctly?** (the core knowledge)
4. **What are the most common mistakes to avoid?** (the "What NOT to Do" section)

### Step 3: Use the Skill Template

Every skill in Noocyte AI follows this exact structure:

```markdown
---
name: [kebab-case-name]
description: >
  [2-3 sentence description. First sentence: what it does.
   Second sentence: when to use it. Third sentence: key constraint or output.]
argument-hint: "<argument description>"
disable-model-invocation: [true/false]
context: [fork/default]
allowed-tools: [Bash, Read, Write, Edit — only what's needed]
---

# [Skill Title]

## Purpose
[1-2 paragraphs explaining why this skill exists and what problem it solves.
Be specific to Noocyte AI, not generic.]

## Sub-Skills
[If this skill has sub-components that can be used independently, list them here.
If not, omit this section.]

## When to Use
[Specific trigger conditions. Use bullet points for clarity.]

## [Core Section 1: The Main Knowledge]
[The primary content — code, patterns, procedures, reference data.
Always include runnable Python code examples with imports.]

## [Core Section 2: Additional Knowledge]
[Supporting content, edge cases, configuration options.]

## What NOT to Do
[3-5 specific anti-patterns with:
- The wrong code (marked ❌)
- Why it's wrong
- The correct code (marked ✅)]

## Testing This Skill
[pytest examples that verify the skill's core functionality works correctly.]

---
*[A memorable one-line principle that captures the skill's philosophy.]*
```

### Step 4: Validate the New Skill

After creating a new skill, run this checklist:

```bash
# Check the skill file exists and is readable
cat .claude/skills/[new-skill-name]/SKILL.md

# Check it follows the naming convention
ls .claude/skills/ | grep [new-skill-name]

# Verify the frontmatter is valid YAML
python3 -c "
import yaml
with open('.claude/skills/[new-skill-name]/SKILL.md') as f:
    content = f.read()
    # Extract frontmatter between --- markers
    parts = content.split('---')
    if len(parts) >= 3:
        yaml.safe_load(parts[1])
        print('✅ Frontmatter is valid YAML')
    else:
        print('❌ No frontmatter found')
"

# Add the new skill to the registry
echo "- [new-skill-name]: [description]" >> .claude/noocyte-skills-v2/README.md
```

### Step 5: Register the Skill

Every new skill must be registered in two places:

1. **`.claude/noocyte-skills-v2/README.md`** — Add to the skills table
2. **`.claude/noocyte-skills-v2/AGENTS.md`** — Add to the agent-to-skill mapping if relevant

---

## Example: Creating a New Skill from Scratch

**Scenario:** You are about to integrate the Cochrane Library API and realize there is no skill for it.

```bash
# Step 1: Check no skill exists
ls .claude/skills/ | grep cochrane
# → (empty — no skill exists)

# Step 2: Create the directory
mkdir -p .claude/skills/cochrane-api

# Step 3: Write the skill (using the template above)
# The skill should cover:
# - Cochrane REST API authentication
# - Searching for systematic reviews
# - Parsing the response format
# - Rate limiting and error handling
# - Integration with the existing RAG pipeline

# Step 4: Validate
cat .claude/skills/cochrane-api/SKILL.md

# Step 5: Register
echo "- **cochrane-api** — Cochrane Library REST API: search, parse, rate-limit" >> .claude/noocyte-skills-v2/README.md
```

---

## The Skill Quality Rubric

Rate every new skill on these dimensions before considering it complete:

| Dimension | Poor (1) | Acceptable (3) | Excellent (5) |
|-----------|----------|----------------|---------------|
| **Specificity** | Generic advice that applies to any project | Some Noocyte-specific context | Deeply specific to Noocyte AI's architecture and constraints |
| **Runnable Code** | No code examples | Pseudocode or incomplete snippets | Complete, importable Python with error handling |
| **Failure Modes** | No "What NOT to Do" | 1-2 generic anti-patterns | 3-5 specific anti-patterns with the exact wrong code and the fix |
| **Testability** | No test examples | Test structure without assertions | Complete pytest tests that can be run immediately |
| **Trigger Clarity** | Vague ("use when needed") | Somewhat specific | Exact conditions that trigger this skill |

**Minimum acceptable score: 15/25 (3 on every dimension)**

---

## Auto-Discovery: Skills That Should Exist

Based on the Noocyte AI architecture, these skills should be created if they don't exist:

```python
SKILLS_THAT_SHOULD_EXIST = [
    # Data pipeline
    "pdf-parser",           # Parsing ICMR PDFs with Marker/PyMuPDF
    "qdrant-operations",    # Qdrant collection management, upsert, search
    "redis-cache",          # Redis semantic caching and DLQ patterns
    
    # Medical domain
    "pico-extractor",       # PICO framework extraction from clinical queries
    "emergency-detector",   # Emergency keyword detection and response
    "drug-interaction",     # Drug-drug interaction checking patterns
    
    # Infrastructure
    "pubsub-patterns",      # Google Cloud Pub/Sub message queue patterns
    "cloud-run-deploy",     # Cloud Run deployment and health checks
    "monitoring-alerts",    # Cloud Monitoring and alerting setup
    
    # Quality
    "prompt-engineering",   # Medical prompt design for Gemini
    "ab-testing",           # A/B testing RAG pipeline changes
]

def check_missing_skills():
    """Identify which required skills don't exist yet."""
    import os
    existing = set(os.listdir(".claude/skills/"))
    missing = [s for s in SKILLS_THAT_SHOULD_EXIST if s not in existing]
    return missing
```

---

## What NOT to Do

```
❌ Creating a skill that is too generic
   Bad: "python-best-practices" (applies to any Python project)
   Good: "noocyte-async-patterns" (specific to Noocyte AI's async architecture)

❌ Creating a skill without runnable code
   Bad: "Use Cohere Rerank API for reranking results"
   Good: Complete Python class with imports, error handling, and tests

❌ Duplicating an existing skill
   Always grep existing skills before creating a new one

❌ Forgetting to register the new skill
   Every skill must be in the README and AGENTS.md to be discoverable

❌ Creating a skill without "What NOT to Do"
   The failure modes are often more valuable than the happy path
```

---

*If you don't have a skill for it, you don't understand it well enough to do it reliably.*
