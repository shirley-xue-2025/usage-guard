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
export PYTHONPATH="${REPO_ROOT}:\${PYTHONPATH:-}"
exec python3 -m usage_guard "\$@"
EOF
chmod +x "${WRAPPER}"

mkdir -p "${HOME}/.usage-guard"

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
