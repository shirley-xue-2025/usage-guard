"""Fixed paths for usage-guard."""

from pathlib import Path

HOME = Path.home()
GUARD_DIR = HOME / ".usage-guard"
CONTROL_PATH = GUARD_DIR / "control.json"
CONFIG_PATH = GUARD_DIR / "config.json"
LOG_PATH = GUARD_DIR / "daemon.log"
PID_PATH = GUARD_DIR / "daemon.pid"
HEARTBEAT_PATH = GUARD_DIR / "heartbeat"
SESSIONS_DIR = GUARD_DIR / "sessions"
LAUNCH_AGENTS_DIR = HOME / "Library" / "LaunchAgents"
LAUNCHD_LABEL = "io.usage-guard.daemon"
LAUNCHD_PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LAUNCHD_LABEL}.plist"

DESKTOP_CLAUDE_DIR = HOME / "Library/Application Support/Claude"
CLAUDE_CREDENTIAL_PATHS = [
    HOME / ".claude" / ".credentials.json",
    HOME / ".claude" / "credentials.json",
    HOME / ".config" / "claude" / "credentials.json",
]
