#!/usr/bin/env bash
# Fail if Ring-2 / personal content would ship in this public repo.
# Used by .githooks/pre-push and CI. Exit 0 = clean.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "public-clean: FAIL — $*" >&2
  exit 1
}

# Must be the shippable clone, not the Ring-2 parent workspace.
basename_root="$(basename "$ROOT")"
if [[ "$basename_root" != "usage-guard" ]]; then
  fail "expected repo root named usage-guard (got ${basename_root})"
fi

# Filenames / trees that belong in the Ring-2 hub only.
FORBIDDEN_PATHS=(
  "SESSION-HANDOVER.md"
  "WORKSPACE.md"
  "marketing-pack.md"
  "medium-draft.md"
  "memory/MEMORY.md"
  "memory/architecture.md"
  "memory/setup-and-troubleshooting.md"
)

for rel in "${FORBIDDEN_PATHS[@]}"; do
  if [[ -e "$ROOT/$rel" ]]; then
    fail "Ring-2 path present in repo tree: $rel (move to parent workspace)"
  fi
  if git ls-files --error-unmatch "$rel" >/dev/null 2>&1; then
    fail "Ring-2 path is tracked: $rel"
  fi
done

# Any tracked path whose basename matches private docs.
while IFS= read -r tracked; do
  [[ -z "$tracked" ]] && continue
  base="$(basename "$tracked")"
  case "$base" in
    SESSION-HANDOVER.md|WORKSPACE.md|marketing-pack.md|medium-draft.md)
      fail "tracked private doc: $tracked"
      ;;
  esac
  case "$tracked" in
    memory/*)
      fail "tracked Ring-2 memory path: $tracked"
      ;;
  esac
done <<EOF
$(git ls-files)
EOF

# Content patterns that must never appear in tracked text.
PATTERN='(/Users/chao\.xue|chao\.xue@|@ablefy\.io|Ring 2|about-me/memory|SESSION-HANDOVER|marketing-pack|medium-draft|Private — not for GitHub|VoC repo)'

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
git ls-files | grep -E '\.(md|py|sh|yml|yaml|json|txt|toml)$' >"$TMP" || true

if [[ -s "$TMP" ]]; then
  # Drop this script from the content scan — it must mention the patterns.
  TMP2="$(mktemp)"
  trap 'rm -f "$TMP" "$TMP2" "$MATCHES"' EXIT
  grep -v 'scripts/check-public-clean\.sh$' "$TMP" >"$TMP2" || true
  mv "$TMP2" "$TMP"

  MATCHES="$(mktemp)"
  trap 'rm -f "$TMP" "$MATCHES"' EXIT
  if [[ ! -s "$TMP" ]]; then
    echo "public-clean: OK"
    exit 0
  fi
  if command -v rg >/dev/null 2>&1; then
    # rg exit 1 = no match (clean); 0 = matches (dirty)
    if xargs rg -n -e "$PATTERN" <"$TMP" >"$MATCHES" 2>/dev/null; then
      cat "$MATCHES" >&2
      fail "forbidden personal/Ring-2 content in tracked files (matches above)"
    fi
  else
    set +e
    # shellcheck disable=SC2046
    grep -nE "$PATTERN" $(cat "$TMP") >"$MATCHES" 2>/dev/null
    rc=$?
    set -e
    if [[ $rc -eq 0 ]]; then
      cat "$MATCHES" >&2
      fail "forbidden personal/Ring-2 content in tracked files (matches above)"
    fi
  fi
fi

echo "public-clean: OK"
