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
        "sleep_until": None,
        "last_reset_at": None,
        "active_session_ids": [],
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
    enrich_time_fields(payload)
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


def parse_reset_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_until_reset(resets_at: str | None, margin: int = 60) -> int | None:
    """Seconds until reset, floored at 0 (for daemon sleep scheduling)."""
    raw = seconds_until_timestamp(resets_at, margin=margin)
    if raw is None:
        return None
    return max(0, raw)


def seconds_until_timestamp(value: str | None, *, margin: int = 0) -> int | None:
    """Signed seconds until an ISO timestamp. Negative means already passed."""
    reset_dt = parse_reset_at(value)
    if not reset_dt:
        return None
    now = datetime.now(timezone.utc)
    if reset_dt.tzinfo is None:
        reset_dt = reset_dt.replace(tzinfo=timezone.utc)
    return int((reset_dt - now).total_seconds() - margin)


def format_local_time(value: str | None) -> str | None:
    """Human-readable local time for sessions and status output."""
    reset_dt = parse_reset_at(value)
    if not reset_dt:
        return None
    return reset_dt.astimezone().strftime("%Y-%m-%d %H:%M %Z")


def enrich_time_fields(control: dict) -> dict:
    """Add precomputed timing fields so sessions never parse UTC themselves."""
    resets_at = control.get("five_hour_resets_at")
    if resets_at:
        sec = seconds_until_timestamp(resets_at, margin=0)
        if sec is not None:
            control["seconds_until_five_hour_reset"] = sec
            control["five_hour_reset_pending"] = sec > 0
        local = format_local_time(resets_at)
        if local:
            control["five_hour_reset_local"] = local

    sleep_until = control.get("sleep_until")
    if sleep_until:
        sec = seconds_until_timestamp(sleep_until, margin=0)
        if sec is not None:
            control["seconds_until_sleep_until"] = sec
        local = format_local_time(sleep_until)
        if local:
            control["sleep_until_local"] = local
    else:
        control.pop("seconds_until_sleep_until", None)
        control.pop("sleep_until_local", None)

    resume_at = control.get("resume_at")
    if resume_at:
        local = format_local_time(resume_at)
        if local:
            control["resume_at_local"] = local

    pending = control.get("five_hour_reset_pending")
    percent = control.get("five_hour_percent")
    if (
        control.get("state") == "RUN"
        and resets_at
        and pending is False
        and percent is not None
    ):
        control["awaiting_post_reset_poll"] = True
        control["percent_note"] = (
            "Window reset time passed; percent may still reflect the old window "
            "until the next daemon poll. Trust state; expect correction at "
            "daemon_next_poll_at."
        )
    else:
        control.pop("awaiting_post_reset_poll", None)
        control.pop("percent_note", None)

    next_poll = control.get("daemon_next_poll_at")
    if isinstance(next_poll, (int, float)):
        poll_dt = datetime.fromtimestamp(next_poll, tz=timezone.utc)
        control["daemon_next_poll_local"] = poll_dt.astimezone().strftime(
            "%Y-%m-%d %H:%M %Z"
        )

    return control


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


def apply_wait_schedule(control: dict, *, margin: int = 60) -> dict:
    """Set session_check_seconds and sleep_until for PAUSE/COOLDOWN waits."""
    state = control.get("state", "RUN")
    percent = control.get("five_hour_percent")
    resets_at = control.get("resume_at") or control.get("five_hour_resets_at")

    if state in {"PAUSE", "COOLDOWN"} and resets_at:
        remaining = seconds_until_reset(resets_at, margin)
        if remaining is not None and remaining > 0:
            control["sleep_until"] = resets_at
            # Cap at 59m so a single /loop sleep covers most of the wait.
            control["session_check_seconds"] = max(60, min(remaining, 59 * 60))
            return control

    control["sleep_until"] = None
    control["session_check_seconds"] = session_check_seconds(percent, state)
    return control


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
