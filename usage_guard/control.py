"""Read/write control.json and checkpoint files."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_guard.paths import CONTROL_PATH, GUARD_DIR, SESSIONS_DIR


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_control(session_id: str | None = None) -> dict:
    return {
        "armed": False,
        "state": "IDLE",
        "five_hour_percent": None,
        "five_hour_resets_at": None,
        "resume_at": None,
        "daemon_next_poll_at": None,
        "session_check_seconds": 600,
        "phase": "idle",
        "warned_at_85": False,
        "updated_at": now_iso(),
        "session_id": session_id,
        "note": "",
    }


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_control(payload: dict) -> None:
    payload["updated_at"] = now_iso()
    write_json_atomic(CONTROL_PATH, payload)


def read_control() -> dict:
    data = read_json(CONTROL_PATH)
    return data if isinstance(data, dict) else default_control()


def new_session_id() -> str:
    return uuid.uuid4().hex[:12]


def session_dir(session_id: str) -> Path:
    return SESSIONS_DIR / session_id


def checkpoint_path(session_id: str) -> Path:
    return session_dir(session_id) / "checkpoint.json"


def default_checkpoint(task: str = "") -> dict:
    return {
        "task": task,
        "done": [],
        "next": None,
        "note": "",
        "updated_at": now_iso(),
    }


def write_checkpoint(session_id: str, payload: dict) -> None:
    payload["updated_at"] = now_iso()
    write_json_atomic(checkpoint_path(session_id), payload)


def read_checkpoint(session_id: str) -> dict | None:
    return read_json(checkpoint_path(session_id))


def load_config() -> dict:
    defaults = {
        "threshold_pause": 90,
        "threshold_warn": 85,
        "cooldown_margin_seconds": 60,
    }
    from usage_guard.paths import CONFIG_PATH

    data = read_json(CONFIG_PATH)
    if isinstance(data, dict):
        defaults.update(data)
    return defaults


def poll_interval_seconds(percent: float | None) -> int:
    if percent is None:
        return 15 * 60
    if percent < 50:
        return 30 * 60
    if percent < 75:
        return 15 * 60
    if percent < 85:
        return 10 * 60
    if percent < 90:
        return 5 * 60
    return 0


def session_check_seconds(percent: float | None, state: str) -> int:
    if state in {"PAUSE", "COOLDOWN"}:
        return 5 * 60
    if percent is None:
        return 10 * 60
    if percent < 75:
        return 15 * 60
    if percent < 85:
        return 10 * 60
    return 5 * 60


def merge_done(existing: list[Any] | None, new_items: list[Any] | None) -> list[Any]:
    """Append unique items to done, preserving order."""
    result = list(existing or [])
    seen = set(result)
    for item in new_items or []:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def ensure_dirs() -> None:
    GUARD_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
