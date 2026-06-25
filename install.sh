#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="${REPO_ROOT}/skill/usage-guard"
SKILL_DEST="${HOME}/.claude/skills/usage-guard"
BIN_DIR="${HOME}/.local/bin"
WRAPPER="${BIN_DIR}/usage-guard"

echo "Installing usage-guard..."

mkdir -p "${HOME}/.claude/skills"
rm -rf "${SKILL_DEST}"
cp -R "${SKILL_SRC}" "${SKILL_DEST}"
chmod +x "${SKILL_DEST}/scripts/"*.sh

mkdir -p "${BIN_DIR}"
cat > "${WRAPPER}" <<EOF
#!/usr/bin/env bash
REPO_ROOT="${REPO_ROOT}"
if [ ! -d "\${REPO_ROOT}/usage_guard" ]; then
  echo "usage-guard: clone not found at \${REPO_ROOT}" >&2
  echo "  Install path is stale (repo moved or deleted)." >&2
  echo "  Fix: cd <your-clone>/usage-guard && ./install.sh && usage-guard doctor" >&2
  exit 1
fi
export PYTHONPATH="\${REPO_ROOT}:\${PYTHONPATH:-}"
exec python3 -m usage_guard "\$@"
EOF
chmod +x "${WRAPPER}"

mkdir -p "${HOME}/.usage-guard"
printf '%s\n' "${REPO_ROOT}" > "${HOME}/.usage-guard/repo-root"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    echo ""
    echo "Add to your shell profile:"
    echo "  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    ;;
esac

echo ""
echo "Installed:"
echo "  skill  -> ${SKILL_DEST}"
echo "  cli    -> ${WRAPPER}"
echo ""
echo "Next steps:"
echo "  1. usage-guard doctor"
echo "  2. In Claude Desktop Code tab: /usage-guard <your long task>"
echo ""
