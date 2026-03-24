#!/bin/bash
# Launch the Hunt AI reranker playground
# Usage: bash scripts/dashboard/run_dashboard.sh

set -e

cd "$(dirname "$0")/../.."   # project root

echo "📦 Installing dashboard dependencies..."
pip install -q -r scripts/dashboard/requirements.txt

echo "🚀 Starting Hunt AI Playground on http://localhost:8501"
streamlit run scripts/dashboard/app.py \
  --server.port 8501 \
  --server.headless false \
  --theme.base dark \
  --theme.primaryColor "#00BFA5"
