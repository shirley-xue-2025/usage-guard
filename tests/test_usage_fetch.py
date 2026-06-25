"""Unit tests for usage parsing (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage_guard.control import apply_usage_telemetry, default_control
from usage_guard.usage_fetch import format_extra_usage, parse_usage


def test_parse_usage_extra_wallet():
    raw = {
        "five_hour": {"utilization": 88.0, "resets_at": "2026-06-20T12:00:00+00:00"},
        "seven_day": {"utilization": 42.0, "resets_at": "2026-06-27T12:00:00+00:00"},
        "extra_usage": {
            "is_enabled": True,
            "monthly_limit": 1700,
            "used_credits": 190.0,
            "utilization": 11.18,
            "currency": "EUR",
        },
    }
    parsed = parse_usage(raw)
    assert parsed["fiveHourPercent"] == 88.0
    assert parsed["extraEnabled"] is True
    assert parsed["extraUsedCredits"] == 190.0
    assert parsed["extraMonthlyLimit"] == 1700.0
    assert parsed["extraUtilization"] == 11.18
    assert parsed["extraCurrency"] == "EUR"


def test_format_extra_usage_enabled_with_spend():
    summary = format_extra_usage(
        {
            "extraEnabled": True,
            "extraUsedCredits": 190.0,
            "extraMonthlyLimit": 1700.0,
            "extraUtilization": 11.18,
            "extraCurrency": "EUR",
        }
    )
    assert summary == "€1.90 / €17.00, 11.2%"


def test_format_extra_usage_disabled():
    assert format_extra_usage({"extraEnabled": False}) == "disabled"


def test_apply_usage_telemetry_writes_extra_fields():
    control = default_control("abc")
    apply_usage_telemetry(
        control,
        {
            "fiveHourPercent": 55.0,
            "fiveHourResetsAt": "2026-06-20T12:00:00+00:00",
            "extraEnabled": True,
            "extraUsedCredits": 50.0,
            "extraMonthlyLimit": 1000.0,
            "extraUtilization": 5.0,
            "extraCurrency": "USD",
        },
    )
    assert control["five_hour_percent"] == 55.0
    assert control["extra_used_credits"] == 50.0
    assert control["extra_monthly_limit"] == 1000.0
    assert control["extra_utilization"] == 5.0
    assert control["extra_currency"] == "USD"
