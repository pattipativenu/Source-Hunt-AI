## Universal Agent Contract

This repository uses a universal-core model: one shared knowledge surface with platform-specific adapters.

Canonical workflow surfaces:
- `skills/` (universal skill surface)
- `agents/` (universal role surface)
- This file `AGENTS.md` (shared orchestration and policy)

Current canonical content lives in:
- `.claude/skills/` (authoritative skill content)
- `.claude/agents/` (authoritative agent role content)
- `.claude/rules/` and `.claude/hooks/` (project safety and enforcement)

Adapter folders:
- `.cursor/` (Cursor bootstrap/rules only)
- `.codex/` (Codex bootstrap only)
- `.gemini/` (Gemini bootstrap only)
- `.claude/` (Claude-native bootstrap + canonical content)

Hard rules:
- Do not duplicate skill or agent logic across platform folders by hand.
- Add or update skill/agent content in one canonical location first, then update adapters.
- Platform folders should contain thin entrypoints that point to shared/canonical files.

Current migrated universal entrypoints:
- Skill: `skills/citation-verifier/SKILL.md` (maps to `.claude/skills/citation-verifier/SKILL.md`)
- Agent: `agents/database-reviewer.md` (maps to `.claude/agents/database-reviewer.md`)

## Graphify

This project has a graphify knowledge graph at `graphify-out/`.

Rules:
- Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md` for god nodes and community structure.
- If `graphify-out/wiki/index.md` exists, navigate it instead of reading raw files.
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"`.
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost).
