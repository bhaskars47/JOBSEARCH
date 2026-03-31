#!/usr/bin/env bash
# Installs a 7 AM daily cron job that runs the job search pipeline.
# Run once: bash scripts/setup_cron.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO_DIR/.venv/bin/python"
LOG="$REPO_DIR/data/pipeline.log"

CRON_CMD="0 7 * * * cd $REPO_DIR && $PYTHON -m src.job_search.main >> $LOG 2>&1"

# Check if entry already exists
if crontab -l 2>/dev/null | grep -qF "src.job_search.main"; then
  echo "Cron job already installed. Current crontab:"
  crontab -l | grep "job_search"
  exit 0
fi

# Add the new entry
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
echo "Cron job installed:"
echo "  $CRON_CMD"
echo ""
echo "Logs will be written to: $LOG"
echo "To remove it later: crontab -e"
