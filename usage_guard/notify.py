"""macOS notifications for usage-guard."""

from __future__ import annotations

import platform
import subprocess


def notify(title: str, message: str) -> None:
    if platform.system() != "Darwin":
        return
    safe_title = title.replace('"', "'")
    safe_message = message.replace('"', "'")
    script = (
        f'display notification "{safe_message}" '
        f'with title "{safe_title}" sound name "Submarine"'
    )
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
    except Exception:
        pass
