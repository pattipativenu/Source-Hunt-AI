#!/bin/sh
set -e

echo "🔍 Validating YAML frontmatter for Claude skills..."
python3 scripts/validate_skill_frontmatter.py --all

echo "✅ Skill YAML frontmatter validation passed."

