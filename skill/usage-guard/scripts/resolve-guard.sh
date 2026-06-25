#!/usr/bin/env bash
# Sourced by skill scripts. Sets GUARD_BIN to the CLI wrapper or "python3 -m usage_guard".

_resolve_guard_lib="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

_resolve_guard_fail() {
  local stale="${1:-}"
  echo "usage-guard: cannot find the usage_guard package." >&2
  echo "  Re-run ./install.sh from your usage-guard clone, then: usage-guard doctor" >&2
  if [ -n "$stale" ]; then
    echo "  Stale install path: ${stale}" >&2
  fi
  return 1
}

# Sets GUARD_BIN. Exits 1 with a helpful message if nothing resolves.
resolve_guard_bin() {
  GUARD_BIN=""

  if [ -n "${USAGE_GUARD_BIN:-}" ]; then
    if command -v "$USAGE_GUARD_BIN" >/dev/null 2>&1 || [ -x "$USAGE_GUARD_BIN" ]; then
      GUARD_BIN="$USAGE_GUARD_BIN"
      return 0
    fi
  fi

  if command -v usage-guard >/dev/null 2>&1; then
    GUARD_BIN="usage-guard"
    return 0
  fi

  local wrapper="${HOME}/.local/bin/usage-guard"
  if [ -x "$wrapper" ]; then
    GUARD_BIN="$wrapper"
    return 0
  fi

  local repo_root=""
  local repo_root_file="${HOME}/.usage-guard/repo-root"
  if [ -f "$repo_root_file" ]; then
    IFS= read -r repo_root < "$repo_root_file" || true
    if [ -n "$repo_root" ] && [ -d "${repo_root}/usage_guard" ]; then
      export PYTHONPATH="${repo_root}:${PYTHONPATH:-}"
      GUARD_BIN="python3 -m usage_guard"
      return 0
    fi
  fi

  local dev_root
  dev_root="$(cd "${_resolve_guard_lib}/../../.." && pwd)"
  if [ -d "${dev_root}/usage_guard" ]; then
    export PYTHONPATH="${dev_root}:${PYTHONPATH:-}"
    GUARD_BIN="python3 -m usage_guard"
    return 0
  fi

  _resolve_guard_fail "$repo_root"
  exit 1
}
