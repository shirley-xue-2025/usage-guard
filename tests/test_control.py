"""Unit tests for control schedule helpers (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone

from usage_guard.control import (
    apply_wait_schedule,
    default_control,
    merge_done,
    poll_interval_seconds,
    session_check_seconds,
)


def test_poll_interval_low_usage():
    assert poll_interval_seconds(10) == 30 * 60
    assert poll_interval_seconds(49) == 30 * 60


def test_poll_interval_mid_usage():
    assert poll_interval_seconds(60) == 15 * 60
    assert poll_interval_seconds(74) == 15 * 60


def test_poll_interval_high_usage():
    assert poll_interval_seconds(80) == 10 * 60
    assert poll_interval_seconds(87) == 5 * 60
    assert poll_interval_seconds(90) == 0


def test_session_check_seconds_pause():
    assert session_check_seconds(50, "PAUSE") == 5 * 60
    assert session_check_seconds(50, "COOLDOWN") == 5 * 60


def test_session_check_seconds_run():
    assert session_check_seconds(40, "RUN") == 15 * 60
    assert session_check_seconds(88, "RUN") == 5 * 60


def test_default_control_has_required_keys():
    c = default_control("abc123")
    assert c["session_id"] == "abc123"
    assert c["state"] == "IDLE"
    assert "session_check_seconds" in c


def test_merge_done_preserves_order_and_dedupes():
    assert merge_done(["a", "b"], ["b", "c"]) == ["a", "b", "c"]
    assert merge_done(None, ["x"]) == ["x"]


def test_apply_wait_schedule_cooldown_uses_reset_time():
    reset_at = (datetime.now(timezone.utc) + timedelta(minutes=100)).isoformat()
    control = {
        "state": "COOLDOWN",
        "five_hour_percent": 94.0,
        "resume_at": reset_at,
    }
    apply_wait_schedule(control, margin=60)
    assert control["sleep_until"] == reset_at
    assert control["session_check_seconds"] == 59 * 60


def test_apply_wait_schedule_run_clears_sleep_until():
    control = {
        "state": "RUN",
        "five_hour_percent": 40.0,
        "sleep_until": "2026-01-01T00:00:00+00:00",
    }
    apply_wait_schedule(control)
    assert control["sleep_until"] is None
    assert control["session_check_seconds"] == 15 * 60
