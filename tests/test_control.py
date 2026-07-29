"""Unit tests for control schedule helpers (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone

from usage_guard.control import (
    apply_telemetry_health,
    apply_wait_schedule,
    checkpoint_session_id,
    default_control,
    effective_state,
    enrich_time_fields,
    merge_done,
    poll_interval_seconds,
    seconds_until_timestamp,
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


def test_seconds_until_timestamp_future():
    future = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    assert seconds_until_timestamp(future, margin=0) > 0


def test_enrich_time_fields_post_reset_poll_lag():
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    control = {
        "state": "RUN",
        "five_hour_resets_at": past,
        "five_hour_percent": 89.0,
    }
    enrich_time_fields(control)
    assert control["five_hour_reset_pending"] is False
    assert control["awaiting_post_reset_poll"] is True
    assert "percent_note" in control


def test_enrich_time_fields_adds_local_and_seconds():
    future = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
    control = {"five_hour_resets_at": future, "state": "RUN"}
    enrich_time_fields(control)
    assert control["five_hour_reset_pending"] is True
    assert control["seconds_until_five_hour_reset"] > 0
    assert "five_hour_reset_local" in control


def test_checkpoint_session_id_prefers_sitting():
    control = {"session_id": "primary", "sitting_session_id": "sitting"}
    assert checkpoint_session_id(control) == "sitting"
    assert checkpoint_session_id(control, "override") == "override"
    assert checkpoint_session_id({"session_id": "only"}) == "only"


def test_apply_telemetry_health_marks_lost_after_three_nulls():
    control: dict = {"consecutive_null_polls": 0, "phase": "normal", "state": "RUN"}
    assert apply_telemetry_health(control, None) is False
    assert apply_telemetry_health(control, None) is False
    assert control.get("telemetry_lost") is not True
    assert apply_telemetry_health(control, None) is True
    assert control["telemetry_lost"] is True
    assert control["state"] == "UNKNOWN"
    assert control["phase"] == "telemetry_lost"
    assert control["telemetry_lost_notified"] is True
    assert control["telemetry_lost_notify_count"] == 1
    # Same poll window: no immediate re-notify
    assert apply_telemetry_health(control, None) is False
    apply_telemetry_health(control, 42.0)
    assert control["telemetry_lost"] is False
    assert control["telemetry_lost_notified"] is False
    assert control["telemetry_lost_notify_count"] == 0


def test_apply_telemetry_health_renotifies_after_backoff():
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    control: dict = {
        "consecutive_null_polls": 3,
        "phase": "telemetry_lost",
        "state": "UNKNOWN",
        "telemetry_lost": True,
        "telemetry_lost_notified": True,
        "telemetry_lost_last_notify_at": past,
        "telemetry_lost_notify_count": 1,
    }
    assert apply_telemetry_health(control, None) is True
    assert control["telemetry_lost_notify_count"] == 2


def test_valid_until_and_effective_state_fail_closed_when_stale():
    past_poll = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    control = {
        "armed": True,
        "state": "RUN",
        "five_hour_percent": 29.0,
        "weekly_percent": None,
        "last_poll_at": past_poll,
        "telemetry_lost": False,
    }
    enrich_time_fields(control)
    assert control["stale"] is True
    assert control["stale_reason"] == "poll_overdue"
    assert control["valid_until"]
    assert effective_state(control) == "UNKNOWN"


def test_valid_until_fresh_when_recent_poll():
    recent = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    control = {
        "armed": True,
        "state": "RUN",
        "five_hour_percent": 29.0,
        "last_poll_at": recent,
        "telemetry_lost": False,
    }
    enrich_time_fields(control)
    assert control["stale"] is False
    assert effective_state(control) == "RUN"


def test_effective_state_unknown_when_telemetry_lost():
    control = {
        "armed": True,
        "state": "RUN",  # legacy fail-open shape
        "telemetry_lost": True,
        "stale": False,
    }
    assert effective_state(control) == "UNKNOWN"


def test_apply_wait_schedule_run_clears_sleep_until():
    control = {
        "state": "RUN",
        "five_hour_percent": 40.0,
        "sleep_until": "2026-01-01T00:00:00+00:00",
    }
    apply_wait_schedule(control)
    assert control["sleep_until"] is None
    assert control["session_check_seconds"] == 15 * 60
