"""macOS LaunchAgent install/load for supervised daemon restarts."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from usage_guard.paths import GUARD_DIR, LAUNCH_AGENTS_DIR, LAUNCHD_LABEL, LAUNCHD_PLIST_PATH

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python}</string>
    <string>-m</string>
    <string>usage_guard.daemon</string>
    <string>--supervised</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{repo_root}</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key>
    <string>{repo_root}</string>
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
  <string>{log_out}</string>
  <key>StandardErrorPath</key>
  <string>{log_err}</string>
</dict>
</plist>
"""


def launchd_supported() -> bool:
    return platform.system() == "Darwin"


def _uid() -> int:
    return os.getuid()


def _domain() -> str:
    return f"gui/{_uid()}"


def _service_target() -> str:
    return f"{_domain()}/{LAUNCHD_LABEL}"


def write_plist(repo_root: Path, *, python: str | None = None) -> Path:
    """Write LaunchAgent plist. Clean exit stays down; crash/kill restarts."""
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    GUARD_DIR.mkdir(parents=True, exist_ok=True)
    python_bin = python or "python3"
    # Prefer absolute interpreter so launchd does not depend on PATH.
    try:
        import sys

        python_bin = sys.executable or python_bin
    except Exception:
        pass
    body = PLIST_TEMPLATE.format(
        label=LAUNCHD_LABEL,
        python=python_bin,
        repo_root=str(repo_root.resolve()),
        log_out=str(GUARD_DIR / "daemon.launchd.out.log"),
        log_err=str(GUARD_DIR / "daemon.launchd.err.log"),
    )
    LAUNCHD_PLIST_PATH.write_text(body, encoding="utf-8")
    return LAUNCHD_PLIST_PATH


def is_loaded() -> bool:
    if not launchd_supported() or not LAUNCHD_PLIST_PATH.exists():
        return False
    try:
        result = subprocess.run(
            ["launchctl", "print", _service_target()],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def bootstrap() -> bool:
    """Load the agent (idempotent). Does not start the daemon until kickstart/arm."""
    if not launchd_supported():
        return False
    if not LAUNCHD_PLIST_PATH.exists():
        return False
    # bootout first so a reinstall picks up a rewritten plist
    subprocess.run(
        ["launchctl", "bootout", _domain(), str(LAUNCHD_PLIST_PATH)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    result = subprocess.run(
        ["launchctl", "bootstrap", _domain(), str(LAUNCHD_PLIST_PATH)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0 or is_loaded()


def kickstart(*, kill: bool = True) -> bool:
    """Start (or restart) the supervised daemon via launchd."""
    if not launchd_supported():
        return False
    if not is_loaded() and not bootstrap():
        return False
    args = ["launchctl", "kickstart"]
    if kill:
        args.append("-k")
    args.append(_service_target())
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False


def bootout() -> bool:
    if not launchd_supported() or not LAUNCHD_PLIST_PATH.exists():
        return False
    result = subprocess.run(
        ["launchctl", "bootout", _domain(), str(LAUNCHD_PLIST_PATH)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0
