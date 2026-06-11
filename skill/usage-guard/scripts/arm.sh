#!/usr/bin/env bash
set -euo pipefail

TASK="${*:-}"
GUARD_BIN="${USAGE_GUARD_BIN:-usage-guard}"

if ! command -v "$GUARD_BIN" >/dev/null 2>&1; then
  REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
  export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
  GUARD_BIN="python3 -m usage_guard"
fi

if [ -n "$TASK" ] && [ "$TASK" != "resume" ]; then
  $GUARD_BIN arm --task "$TASK"
else
  $GUARD_BIN arm
fi
