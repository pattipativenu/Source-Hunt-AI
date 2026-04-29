---
name: citation-verifier
description: Universal skill entry for post-generation citation verification workflows. Use for claim decomposition, entailment checks, citation correction, and unsupported-claim handling.
canonical_source: .claude/skills/citation-verifier/SKILL.md
status: migrated-entrypoint
---

# Citation Verifier (Universal Entry)

This is the universal entrypoint for citation verification across Claude, Cursor, Codex, and Gemini adapters.

Canonical full implementation currently lives in:
- `.claude/skills/citation-verifier/SKILL.md`

Scope:
- Decompose answers into atomic claims with citation markers.
- Verify claim-source support with entailment scoring.
- Correct failed citations using retrieved context.
- Remove or flag unsupported claims before delivery.
- Enforce stricter medical thresholding and DOI existence checks.

Migration note:
- Keep this universal entrypoint stable.
- Maintain detailed implementation in one canonical source until full consolidation is completed.
