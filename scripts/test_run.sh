#!/usr/bin/env bash
# Manual one-shot pipeline run (no email sent).
# Usage: bash scripts/test_run.sh
#        bash scripts/test_run.sh --send-email   (include email)

set -e
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"

cd "$REPO_DIR"

if [[ "$1" == "--send-email" ]]; then
  echo "Running pipeline WITH email..."
  $PYTHON -m src.job_search.main
else
  echo "Running pipeline in dry-run mode (no email)..."
  $PYTHON -m src.job_search.main --dry-run
fi
