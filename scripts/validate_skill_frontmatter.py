#!/usr/bin/env python3
"""
Validate YAML frontmatter in Claude skill files.

Why: some skill loaders parse the frontmatter as YAML; if `description:` contains
colon tokens without proper quoting/folding, YAML parsing breaks and tools surface
errors (e.g. "mapping values are not allowed in this context").

This script is intended for pre-commit enforcement.
"""

from __future__ import annotations

import argparse
import subprocess
import re
from pathlib import Path
from typing import Any


def extract_yaml_frontmatter(text: str) -> dict[str, Any]:
    """
    Extract the first YAML frontmatter block:

    ---
    <yaml>
    ---
    """
    normalized = text.replace("\r\n", "\n")
    match = re.match(r"^---\n(.*?)\n---\n", normalized, flags=re.DOTALL)
    if not match:
        raise ValueError("Missing or malformed YAML frontmatter block (expected leading '---' ... closing '---').")

    fm = match.group(1)
    try:
        import yaml  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError("PyYAML is required to validate skill frontmatter.") from e

    parsed = yaml.safe_load(fm)
    if not isinstance(parsed, dict):
        raise ValueError("Frontmatter must parse into a YAML mapping/object.")

    return parsed


def validate_skill_file(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{path}: read error: {e}"]

    try:
        frontmatter = extract_yaml_frontmatter(text)
    except Exception as e:
        return [f"{path}: {e}"]

    required_keys = ["name", "description"]
    errors: list[str] = []
    for k in required_keys:
        v = frontmatter.get(k)
        if v is None:
            errors.append(f"{path}: frontmatter missing required key '{k}'")
        elif not isinstance(v, str) or not v.strip():
            errors.append(f"{path}: frontmatter '{k}' must be a non-empty string")

    return errors


def staged_skill_files(repo_root: Path) -> list[Path]:
    cmd = ["git", "diff", "--cached", "--name-only"]
    try:
        out = subprocess.check_output(cmd, cwd=repo_root)
    except Exception:
        return []

    files: set[Path] = set()
    for line in out.decode("utf-8", errors="replace").splitlines():
        rel = line.strip()
        if rel.startswith(".claude/skills/") and rel.endswith("SKILL.md"):
            files.add(repo_root / rel)
    return sorted(files)


def all_skill_files() -> list[Path]:
    root = Path(".claude/skills")
    if not root.exists():
        return []
    return sorted(root.rglob("SKILL.md"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--staged", action="store_true", help="Validate only staged skill files (fast).")
    parser.add_argument("--all", action="store_true", help="Validate all skill files (slower).")
    args = parser.parse_args()

    if not args.staged and not args.all:
        args.staged = True

    repo_root = Path(__file__).resolve().parents[1]
    files = staged_skill_files(repo_root) if args.staged else all_skill_files()
    if not files:
        return 0

    errors: list[str] = []
    for p in files:
        errors.extend(validate_skill_file(p))

    if errors:
        print("❌ Skill YAML frontmatter validation failed:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(f"✅ Skill YAML frontmatter OK ({len(files)} file(s)).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

