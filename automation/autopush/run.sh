#!/usr/bin/env bash
# Local daemon runner for the auto-push automation.
# Runs one cycle immediately, then every AUTOPUSH_INTERVAL seconds (default 300).
set -u

DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="${AUTOPUSH_REPO_DIR:-$(cd "$DIR/../.." && pwd)}"
INTERVAL="${AUTOPUSH_INTERVAL:-300}"
LOG="${AUTOPUSH_LOG:-$DIR/autopush.log}"

export AUTOPUSH_REPO_DIR="$REPO_DIR"
export AUTOPUSH_INTERVAL="$INTERVAL"
export AUTOPUSH_BRANCH="${AUTOPUSH_BRANCH:-main}"

echo "[$(date -u +%FT%TZ)] starting autopush daemon: repo=$REPO_DIR interval=${INTERVAL}s log=$LOG" >>"$LOG"
exec python3 "$DIR/main.py" --daemon >>"$LOG" 2>&1
