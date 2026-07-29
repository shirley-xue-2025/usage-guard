"""Read/write control.json and checkpoint files."""

from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from usage_guard.paths import CONTROL_PATH, GUARD_DIR, HEARTBEAT_PATH, SESSIONS_DIR

# How long after the expected next poll a control.json stays trustworthy.
VALID_UNTIL_GRACE_SECONDS = 120
# Blind-alert cadence: immediate, then hourly ×3, then daily.
TELEMETRY_NOTIFY_HOURLY_CAP = 4
TELEMETRY_NOTIFY_HOURLY_SECONDS = 3600
TELEMETRY_NOTIFY_DAILY_SECONDS = 86400


def now_iso() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def default_control(session_id: str | None = None) -> dict:
    return {
        "armed": False,
        "state": "IDLE",
        "five_hour_percent": None,
        "five_hour_resets_at": None,
        "weekly_percent": None,
        "weekly_resets_at": None,
        "pause_reason": None,
        "extra_enabled": None,
        "extra_used_credits": None,
        "extra_monthly_limit": None,
        "extra_utilization": None,
        "extra_currency": None,
        "resume_at": None,
        "sleep_until": None,
        "last_reset_at": None,
        "last_poll_at": None,
        "valid_until": None,
        "stale": False,
        "stale_reason": None,
        "active_session_ids": [],
        "sitting_session_id": None,
        "daemon_next_poll_at": None,
        "consecutive_null_polls": 0,
        "telemetry_lost": False,
        "telemetry_lost_notified": False,
        "telemetry_lost_last_notify_at": None,
        "telemetry_lost_notify_count": 0,
        "session_check_seconds": 600,
        "phase": "idle",
        "warned_at_85": False,
        "warned_at_weekly": False,
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


def touch_heartbeat() -> None:
    """Liveness signal for consumers that cannot inspect processes."""
    try:
        GUARD_DIR.mkdir(parents=True, exist_ok=True)
        HEARTBEAT_PATH.write_text(now_iso() + "\n", encoding="utf-8")
    except OSError:
        pass


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


def checkpoint_session_id(control: dict, override: str | None = None) -> str | None:
    """Which session's checkpoint to read/write (join sets sitting_session_id)."""
    if override:
        return override
    sitting = control.get("sitting_session_id")
    if sitting:
        return sitting
    return control.get("session_id")


def load_config() -> dict:
    defaults = {
        "threshold_pause": 90,
        "threshold_warn": 85,
        "weekly_enabled": False,
        "weekly_threshold_pause": 98,
        "weekly_threshold_warn": 95,
        "weekly_pause_within_hours": None,
        "cooldown_margin_seconds": 60,
    }
    from usage_guard.paths import CONFIG_PATH

    data = read_json(CONFIG_PATH)
    if isinstance(data, dict):
        defaults.update(data)
    return defaults


def limits_config(config: dict) -> dict:
    """Normalized limit thresholds from config.json."""
    return {
        "five_hour_pause": config.get("threshold_pause", 90),
        "five_hour_warn": config.get("threshold_warn", 85),
        "weekly_enabled": bool(config.get("weekly_enabled", False)),
        "weekly_pause": config.get("weekly_threshold_pause", 98),
        "weekly_warn": config.get("weekly_threshold_warn", 95),
        "weekly_pause_within_hours": config.get("weekly_pause_within_hours"),
    }


def weekly_pause_applies(control: dict, config: dict) -> bool:
    """Weekly % alone triggers PAUSE only when reset is within the configured window.

    If weekly_pause_within_hours is null, any weekly >= threshold pauses (v0.2.0 behavior).
    """
    within_hours = config.get("weekly_pause_within_hours")
    if within_hours is None:
        return True
    resets_at = control.get("weekly_resets_at")
    if not resets_at:
        return True
    sec = seconds_until_timestamp(resets_at, margin=0)
    if sec is None:
        return True
    return sec <= int(within_hours) * 3600


def effective_poll_percent(control: dict, config: dict) -> float | None:
    """Highest relevant utilization — drives poll cadence when weekly is enabled."""
    limits = limits_config(config)
    values: list[float] = []
    fh = control.get("five_hour_percent")
    if fh is not None:
        values.append(float(fh))
    if limits["weekly_enabled"]:
        wk = control.get("weekly_percent")
        if wk is not None:
            values.append(float(wk))
    return max(values) if values else None


def limit_hits(control: dict, config: dict) -> dict[str, bool]:
    limits = limits_config(config)
    fh = control.get("five_hour_percent")
    wk = control.get("weekly_percent")
    five_hour = fh is not None and fh >= limits["five_hour_pause"]
    weekly = (
        limits["weekly_enabled"]
        and wk is not None
        and wk >= limits["weekly_pause"]
        and weekly_pause_applies(control, config)
    )
    return {"five_hour": five_hour, "weekly": weekly, "any": five_hour or weekly}


def pause_reason_from_hits(hits: dict[str, bool]) -> str | None:
    if hits.get("five_hour") and hits.get("weekly"):
        return "both"
    if hits.get("five_hour"):
        return "five_hour"
    if hits.get("weekly"):
        return "weekly"
    return None


def can_resume(control: dict, config: dict) -> bool:
    """True when no active limit is at or above its pause threshold."""
    limits = limits_config(config)
    fh = control.get("five_hour_percent")
    if fh is not None and fh >= limits["five_hour_pause"]:
        return False
    if limits["weekly_enabled"]:
        wk = control.get("weekly_percent")
        if wk is not None and wk >= limits["weekly_pause"]:
            if weekly_pause_applies(control, config):
                return False
    return True


def resume_at_for_pause(control: dict, hits: dict[str, bool]) -> str | None:
    """Reset timestamp to wait for when entering PAUSE/COOLDOWN."""
    candidates: list[str] = []
    if hits.get("five_hour"):
        value = control.get("five_hour_resets_at")
        if value:
            candidates.append(value)
    if hits.get("weekly"):
        value = control.get("weekly_resets_at")
        if value:
            candidates.append(value)
    if not candidates:
        return control.get("five_hour_resets_at") or control.get("weekly_resets_at")
    if len(candidates) == 1:
        return candidates[0]
    # Both limits over — wait until the later reset, then re-poll.
    parsed = [(c, parse_reset_at(c)) for c in candidates]
    parsed = [(c, dt) for c, dt in parsed if dt is not None]
    if not parsed:
        return candidates[0]
    return max(parsed, key=lambda item: item[1])[0]


def pause_note(reason: str | None, control: dict, config: dict) -> str:
    limits = limits_config(config)
    fh = control.get("five_hour_percent")
    wk = control.get("weekly_percent")
    if reason == "both":
        return f"five_hour >= {limits['five_hour_pause']}% and weekly >= {limits['weekly_pause']}%"
    if reason == "weekly":
        within = config.get("weekly_pause_within_hours")
        window = f", reset within {within}h" if within is not None else ""
        return (
            f"weekly >= {limits['weekly_pause']}% ({wk:.0f}%){window}"
            if wk is not None
            else "weekly limit"
        )
    return f"five_hour >= {limits['five_hour_pause']}% ({fh:.0f}%)" if fh is not None else "five_hour limit"


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


def apply_valid_until(control: dict, config: dict | None = None) -> dict:
    """Emit freshness contract: last_poll_at + expected interval + grace.

    Consumers: if now > valid_until, treat the file as UNKNOWN regardless of state.
    """
    last_poll = control.get("last_poll_at")
    if not last_poll or not control.get("armed"):
        control["valid_until"] = None
        control["stale"] = bool(control.get("armed")) and not last_poll
        control["stale_reason"] = "never_polled" if control.get("stale") else None
        control.pop("valid_until_local", None)
        control.pop("seconds_until_valid_until", None)
        return control

    if config is None:
        config = load_config()
    interval = poll_interval_seconds(effective_poll_percent(control, config))
    if interval <= 0:
        interval = 60
    last_dt = parse_reset_at(last_poll)
    if last_dt is None:
        control["valid_until"] = None
        control["stale"] = True
        control["stale_reason"] = "invalid_last_poll_at"
        return control
    if last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)

    valid_dt = last_dt + timedelta(seconds=interval + VALID_UNTIL_GRACE_SECONDS)
    control["valid_until"] = valid_dt.astimezone().replace(microsecond=0).isoformat()
    local = format_local_time(control["valid_until"])
    if local:
        control["valid_until_local"] = local
    sec = seconds_until_timestamp(control["valid_until"], margin=0)
    if sec is not None:
        control["seconds_until_valid_until"] = sec
        control["stale"] = sec < 0
        control["stale_reason"] = "poll_overdue" if sec < 0 else None
    else:
        control["stale"] = False
        control["stale_reason"] = None
    return control


def effective_state(control: dict) -> str:
    """State consumers should obey — fails closed on blindness or staleness."""
    if control.get("stale") or control.get("telemetry_lost"):
        return "UNKNOWN"
    if control.get("valid_until"):
        sec = seconds_until_timestamp(control.get("valid_until"), margin=0)
        if sec is not None and sec < 0:
            return "UNKNOWN"
    state = control.get("state")
    return state if state else "UNKNOWN"


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

    weekly_resets_at = control.get("weekly_resets_at")
    if weekly_resets_at:
        sec = seconds_until_timestamp(weekly_resets_at, margin=0)
        if sec is not None:
            control["seconds_until_weekly_reset"] = sec
            control["weekly_reset_pending"] = sec > 0
        local = format_local_time(weekly_resets_at)
        if local:
            control["weekly_reset_local"] = local

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

    apply_valid_until(control)
    control["effective_state"] = effective_state(control)

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


def apply_usage_telemetry(control: dict, usage: dict) -> None:
    """Copy account usage fields from a get_usage() payload into control.json."""
    control["five_hour_percent"] = usage.get("fiveHourPercent")
    control["five_hour_resets_at"] = usage.get("fiveHourResetsAt")
    control["weekly_percent"] = usage.get("weeklyPercent")
    control["weekly_resets_at"] = usage.get("weeklyResetsAt")
    control["extra_enabled"] = usage.get("extraEnabled")
    control["extra_used_credits"] = usage.get("extraUsedCredits")
    control["extra_monthly_limit"] = usage.get("extraMonthlyLimit")
    control["extra_utilization"] = usage.get("extraUtilization")
    control["extra_currency"] = usage.get("extraCurrency")


def apply_wait_schedule(
    control: dict, *, margin: int = 60, config: dict | None = None
) -> dict:
    """Set session_check_seconds and sleep_until for PAUSE/COOLDOWN waits."""
    state = control.get("state", "RUN")
    if config is None:
        config = load_config()
    percent = effective_poll_percent(control, config)
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


def _telemetry_notify_due(control: dict) -> bool:
    """Re-alert on backoff: immediate, hourly ×3, then daily."""
    last = control.get("telemetry_lost_last_notify_at")
    if not last:
        return True
    elapsed = seconds_until_timestamp(last, margin=0)
    if elapsed is None:
        return True
    # seconds_until is negative when last is in the past; want age in seconds.
    age = -elapsed
    count = int(control.get("telemetry_lost_notify_count") or 0)
    interval = (
        TELEMETRY_NOTIFY_HOURLY_SECONDS
        if count < TELEMETRY_NOTIFY_HOURLY_CAP
        else TELEMETRY_NOTIFY_DAILY_SECONDS
    )
    return age >= interval


def apply_telemetry_health(control: dict, percent: float | None) -> bool:
    """Track blind polls when the usage API returns null percent.

    Fail closed: state becomes UNKNOWN while blind (never advertise RUN).
    Returns True when a user alert should fire (first loss or backoff re-alert).
    """
    if percent is not None:
        control["consecutive_null_polls"] = 0
        control["telemetry_lost"] = False
        control["telemetry_lost_notified"] = False
        control["telemetry_lost_last_notify_at"] = None
        control["telemetry_lost_notify_count"] = 0
        if control.get("phase") == "telemetry_lost":
            control["phase"] = "normal"
        # State transitions (UNKNOWN→RUN/PAUSE) are owned by update_control_from_usage.
        return False

    n = int(control.get("consecutive_null_polls") or 0) + 1
    control["consecutive_null_polls"] = n
    if n >= 3:
        control["telemetry_lost"] = True
        control["state"] = "UNKNOWN"
        control["phase"] = "telemetry_lost"
        control["note"] = (
            "usage API returned no 5h percent — guard is blind; "
            "run claude login or usage-guard doctor"
        )
        if _telemetry_notify_due(control):
            control["telemetry_lost_notified"] = True
            control["telemetry_lost_last_notify_at"] = now_iso()
            control["telemetry_lost_notify_count"] = (
                int(control.get("telemetry_lost_notify_count") or 0) + 1
            )
            return True
    return False


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
