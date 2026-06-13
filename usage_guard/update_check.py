"""Optional GitHub version check (cached, non-blocking)."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from usage_guard import __version__

REPO = "shirley-xue-2025/usage-guard"
CACHE_PATH = Path.home() / ".usage-guard" / "update_check.json"
CACHE_TTL_SECONDS = 24 * 60 * 60


def _parse_version(value: str) -> tuple[int, ...]:
    parts: list[int] = []
    for piece in value.lstrip("v").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            break
    return tuple(parts) if parts else (0,)


def _fetch_latest_tag() -> str | None:
    headers = ["-H", "Accept: application/vnd.github+json"]
    urls = [
        f"https://api.github.com/repos/{REPO}/releases/latest",
        f"https://api.github.com/repos/{REPO}/tags",
    ]
    for url in urls:
        try:
            result = subprocess.run(
                ["curl", "-sf", "--max-time", "5", url, *headers],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict) and data.get("tag_name"):
                return str(data["tag_name"]).lstrip("v")
            if isinstance(data, list) and data:
                name = data[0].get("name") or data[0].get("tag_name")
                if name:
                    return str(name).lstrip("v")
        except Exception:
            continue
    return None


def check_for_update(*, force: bool = False) -> dict | None:
    if os.environ.get("USAGE_GUARD_NO_UPDATE_CHECK"):
        return None

    now = time.time()
    if CACHE_PATH.exists() and not force:
        try:
            cached = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            if now - float(cached.get("checked_at", 0)) < CACHE_TTL_SECONDS:
                return cached.get("result")
        except Exception:
            pass

    latest = _fetch_latest_tag()
    local = __version__.lstrip("v")
    if not latest:
        return None

    info = {
        "update_available": _parse_version(latest) > _parse_version(local),
        "latest": latest,
        "local": local,
        "upgrade_hint": "cd <your-clone>/usage-guard && git pull && ./install.sh",
    }
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(
            json.dumps({"checked_at": now, "result": info}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass
    return info


def print_update_notice(info: dict | None) -> None:
    if not info or not info.get("update_available"):
        return
    print()
    print(f"Update available: v{info['latest']} (installed v{info['local']})")
    print(f"  {info['upgrade_hint']}")
    print("  Skill + CLI both refresh on reinstall. Disable: USAGE_GUARD_NO_UPDATE_CHECK=1")
