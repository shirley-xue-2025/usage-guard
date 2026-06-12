"""Unit tests for control schedule helpers (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage_guard.control import (
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
