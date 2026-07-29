#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
SKILL_SRC="${REPO_ROOT}/skill/usage-guard"
SKILL_DEST="${HOME}/.claude/skills/usage-guard"
BIN_DIR="${HOME}/.local/bin"
WRAPPER="${BIN_DIR}/usage-guard"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LAUNCHD_LABEL="io.usage-guard.daemon"
LAUNCHD_PLIST="${LAUNCH_AGENTS_DIR}/${LAUNCHD_LABEL}.plist"

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

# Maintainer clones: enable pre-push public-clean check (Ring-2 leak guard).
if [[ -d "${REPO_ROOT}/.git" && -x "${REPO_ROOT}/.githooks/pre-push" ]]; then
  if git -C "${REPO_ROOT}" config --local core.hooksPath >/dev/null 2>&1; then
    :
  else
    git -C "${REPO_ROOT}" config --local core.hooksPath .githooks
    echo "  hooks  -> core.hooksPath=.githooks (public-clean on push)"
  fi
fi

# LaunchAgent: KeepAlive restarts on crash/kill; clean exit (disarm) stays down.
if [[ "$(uname -s)" == "Darwin" ]]; then
  mkdir -p "${LAUNCH_AGENTS_DIR}"
  PYTHON_BIN="$(command -v python3)"
  cat > "${LAUNCHD_PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LAUNCHD_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>-m</string>
    <string>usage_guard.daemon</string>
    <string>--supervised</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>${REPO_ROOT}</string>
  </dict>
  <key>RunAtLoad</key>
  <false/>
  <key>KeepAlive</key>
  <dict>
    <key>SuccessfulExit</key>
    <false/>
  </dict>
  <key>ThrottleInterval</key>
  <integer>10</integer>
  <key>StandardOutPath</key>
  <string>${HOME}/.usage-guard/daemon.launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/.usage-guard/daemon.launchd.err.log</string>
</dict>
</plist>
EOF
  UID_NUM="$(id -u)"
  launchctl bootout "gui/${UID_NUM}" "${LAUNCHD_PLIST}" >/dev/null 2>&1 || true
  if launchctl bootstrap "gui/${UID_NUM}" "${LAUNCHD_PLIST}"; then
    echo "  launchd -> ${LAUNCHD_PLIST} (KeepAlive; crash restarts, disarm stays down)"
  else
    echo "  warning: LaunchAgent plist written but bootstrap failed — arm will use Popen fallback" >&2
  fi
fi

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
