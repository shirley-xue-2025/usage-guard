#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=resolve-guard.sh
source "${SCRIPT_DIR}/resolve-guard.sh"

resolve_guard_bin
$GUARD_BIN status
