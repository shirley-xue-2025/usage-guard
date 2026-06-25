#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=resolve-guard.sh
source "${SCRIPT_DIR}/resolve-guard.sh"

TASK="${*:-}"
resolve_guard_bin

if [ -n "$TASK" ] && [ "$TASK" != "resume" ]; then
  $GUARD_BIN arm --task "$TASK"
else
  $GUARD_BIN arm
fi
