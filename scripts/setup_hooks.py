#!/usr/bin/env python3
"""
Install local git hooks required for this repository's Claude workflow.

Developers can run:
  python3 scripts/setup_hooks.py

to install `.claude/hooks/pre-commit-script.sh` into `.git/hooks/pre-commit`.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        print("❌ Not a git repository (missing .git directory).")
        return 1

    src = repo_root / ".claude" / "hooks" / "pre-commit-script.sh"
    if not src.exists():
        print(f"❌ Missing hook source: {src}")
        return 1

    dst = git_dir / "hooks" / "pre-commit"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

    # Ensure executable.
    st = os.stat(dst)
    os.chmod(dst, st.st_mode | stat.S_IEXEC)

    print("✅ Installed pre-commit hook.")
    print(f"   Source: {src}")
    print(f"   Target: {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

