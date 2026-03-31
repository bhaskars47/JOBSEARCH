#!/usr/bin/env bash
cd "$(dirname "$0")"
exec .venv/bin/python -m src.job_search.output.dashboard
