"""Unit tests for weekly + dual-threshold limit logic (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone

from usage_guard.control import (
    apply_usage_telemetry,
    apply_wait_schedule,
    can_resume,
    default_control,
    effective_poll_percent,
    enrich_time_fields,
    limit_hits,
    limits_config,
    load_config,
    pause_reason_from_hits,
    resume_at_for_pause,
)
from usage_guard.daemon import update_control_from_usage


def _future_iso(minutes: int = 60) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def _config(*, weekly_enabled: bool = True) -> dict:
    return {
        "threshold_pause": 90,
        "threshold_warn": 85,
        "weekly_enabled": weekly_enabled,
        "weekly_threshold_pause": 98,
        "weekly_threshold_warn": 95,
        "cooldown_margin_seconds": 60,
    }


def _usage(
    *,
    five_hour: float = 60.0,
    weekly: float = 50.0,
    five_resets: str | None = None,
    weekly_resets: str | None = None,
) -> dict:
    return {
        "fiveHourPercent": five_hour,
        "fiveHourResetsAt": five_resets or _future_iso(30),
        "weeklyPercent": weekly,
        "weeklyResetsAt": weekly_resets or _future_iso(90),
        "extraEnabled": None,
        "extraUsedCredits": None,
        "extraMonthlyLimit": None,
        "extraUtilization": None,
        "extraCurrency": None,
    }


def test_apply_usage_telemetry_writes_weekly_fields():
    control = default_control("abc")
    apply_usage_telemetry(
        control,
        {
            "fiveHourPercent": 55.0,
            "fiveHourResetsAt": "2026-06-20T12:00:00+00:00",
            "weeklyPercent": 97.0,
            "weeklyResetsAt": "2026-06-25T23:00:00+00:00",
        },
    )
    assert control["weekly_percent"] == 97.0
    assert control["weekly_resets_at"] == "2026-06-25T23:00:00+00:00"


def test_limit_hits_weekly_only_when_enabled():
    control = {"five_hour_percent": 60.0, "weekly_percent": 98.0}
    hits = limit_hits(control, _config(weekly_enabled=True))
    assert hits == {"five_hour": False, "weekly": True, "any": True}
    assert pause_reason_from_hits(hits) == "weekly"

    disabled = limit_hits(control, _config(weekly_enabled=False))
    assert disabled["any"] is False


def test_limit_hits_five_hour_or_weekly_either_triggers():
    control = {"five_hour_percent": 92.0, "weekly_percent": 70.0}
    hits = limit_hits(control, _config())
    assert hits["five_hour"] is True
    assert hits["weekly"] is False
    assert pause_reason_from_hits(hits) == "five_hour"

    control = {"five_hour_percent": 60.0, "weekly_percent": 99.0}
    hits = limit_hits(control, _config())
    assert pause_reason_from_hits(hits) == "weekly"

    control = {"five_hour_percent": 91.0, "weekly_percent": 98.5}
    hits = limit_hits(control, _config())
    assert pause_reason_from_hits(hits) == "both"


def test_weekly_pause_skipped_when_reset_beyond_within_hours():
    config = _config()
    config["weekly_pause_within_hours"] = 5
    control = {
        "five_hour_percent": 60.0,
        "weekly_percent": 99.0,
        "weekly_resets_at": _future_iso(600),  # 10h out
    }
    hits = limit_hits(control, config)
    assert hits["weekly"] is False
    assert hits["any"] is False


def test_weekly_pause_applies_when_reset_within_hours():
    config = _config()
    config["weekly_pause_within_hours"] = 5
    control = {
        "five_hour_percent": 60.0,
        "weekly_percent": 98.0,
        "weekly_resets_at": _future_iso(120),  # 2h out
    }
    hits = limit_hits(control, config)
    assert hits["weekly"] is True
    assert pause_reason_from_hits(hits) == "weekly"


def test_update_control_stays_run_when_weekly_high_but_reset_far():
    control = default_control("sess")
    control["state"] = "RUN"
    config = _config()
    config["weekly_pause_within_hours"] = 5

    update_control_from_usage(
        control,
        _usage(five_hour=60.0, weekly=99.0, weekly_resets=_future_iso(600)),
        config=config,
    )

    assert control["state"] == "RUN"
    assert control.get("pause_reason") is None


def test_can_resume_requires_both_limits_clear():
    config = _config()
    assert can_resume({"five_hour_percent": 60.0, "weekly_percent": 97.0}, config)
    assert not can_resume({"five_hour_percent": 91.0, "weekly_percent": 97.0}, config)
    assert not can_resume({"five_hour_percent": 60.0, "weekly_percent": 98.0}, config)
    assert not can_resume({"five_hour_percent": 92.0, "weekly_percent": 99.0}, config)


def test_effective_poll_percent_uses_max_of_enabled_limits():
    config = _config()
    control = {"five_hour_percent": 60.0, "weekly_percent": 97.0}
    assert effective_poll_percent(control, config) == 97.0
    assert effective_poll_percent(
        {"five_hour_percent": 80.0, "weekly_percent": 50.0}, config
    ) == 80.0


def test_resume_at_for_weekly_pause():
    fh_reset = _future_iso(30)
    wk_reset = _future_iso(90)
    control = {
        "five_hour_resets_at": fh_reset,
        "weekly_resets_at": wk_reset,
    }
    weekly_only = resume_at_for_pause(control, {"five_hour": False, "weekly": True})
    assert weekly_only == wk_reset

    both = resume_at_for_pause(control, {"five_hour": True, "weekly": True})
    assert both == wk_reset


def test_update_control_pauses_on_weekly_while_five_hour_safe():
    control = default_control("sess")
    control["state"] = "RUN"
    control["armed"] = True
    config = _config()

    update_control_from_usage(
        control,
        _usage(five_hour=60.0, weekly=98.0),
        config=config,
    )

    assert control["state"] == "PAUSE"
    assert control["pause_reason"] == "weekly"
    assert control["resume_at"] == control["weekly_resets_at"]


def test_update_control_stays_run_when_weekly_below_threshold():
    control = default_control("sess")
    control["state"] = "RUN"
    config = _config()

    update_control_from_usage(
        control,
        _usage(five_hour=60.0, weekly=97.0),
        config=config,
    )

    assert control["state"] == "RUN"
    assert control.get("pause_reason") is None


def test_update_control_resumes_after_five_hour_reset_while_weekly_high():
    control = default_control("sess")
    control["state"] = "PAUSE"
    control["pause_reason"] = "five_hour"
    config = _config()

    update_control_from_usage(
        control,
        _usage(five_hour=10.0, weekly=97.0),
        config=config,
    )

    assert control["state"] == "RUN"


def test_enrich_time_fields_weekly_reset_local():
    future = _future_iso(45)
    control = {"weekly_resets_at": future, "state": "RUN"}
    enrich_time_fields(control)
    assert control["weekly_reset_pending"] is True
    assert control["seconds_until_weekly_reset"] > 0
    assert "weekly_reset_local" in control


def test_load_config_weekly_code_defaults():
    cfg = limits_config({})
    assert cfg["weekly_enabled"] is False
    assert cfg["weekly_pause"] == 98


def test_apply_wait_schedule_weekly_cooldown_uses_resume_at():
    reset_at = _future_iso(100)
    control = {
        "state": "COOLDOWN",
        "five_hour_percent": 60.0,
        "weekly_percent": 99.0,
        "pause_reason": "weekly",
        "resume_at": reset_at,
    }
    apply_wait_schedule(control, config=_config())
    assert control["sleep_until"] == reset_at
    assert control["session_check_seconds"] == 59 * 60


def test_update_control_null_percent_sets_unknown_after_three():
    control = default_control("blind")
    control["armed"] = True
    control["state"] = "RUN"
    null_usage = {
        "fiveHourPercent": None,
        "fiveHourResetsAt": None,
        "weeklyPercent": None,
        "weeklyResetsAt": None,
        "extraEnabled": None,
        "extraUsedCredits": None,
        "extraMonthlyLimit": None,
        "extraUtilization": None,
        "extraCurrency": None,
    }
    cfg = _config(weekly_enabled=False)
    for _ in range(3):
        update_control_from_usage(control, null_usage, config=cfg)
    assert control["telemetry_lost"] is True
    assert control["state"] == "UNKNOWN"
    assert control.get("last_poll_at")

