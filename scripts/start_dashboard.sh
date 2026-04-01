#!/usr/bin/env bash
# Auto-starts the JobSearch dashboard and opens it in the browser.
# Called by macOS Launch Agent on login.

set -e

REPO_DIR="/Users/bhaskar.srivastava/.gemini/antigravity/scratch/bhaskars47/JOBSEARCH"
PYTHON="$REPO_DIR/.venv/bin/python"
PORT=5100
LOG="$REPO_DIR/data/dashboard.log"
PID_FILE="$REPO_DIR/data/dashboard.pid"

# Don't start if already running
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Dashboard already running (PID $(cat "$PID_FILE"))" >> "$LOG"
else
    # Start Flask dashboard in background
    cd "$REPO_DIR"
    nohup "$PYTHON" -m src.job_search.output.dashboard >> "$LOG" 2>&1 &
    echo $! > "$PID_FILE"
    echo "Dashboard started (PID $!) at $(date)" >> "$LOG"
fi

# Wait a moment for the server to boot, then open in browser
sleep 3
open "http://localhost:${PORT}"
