"""Tests for version comparison (no network)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from usage_guard.update_check import _parse_version


def test_parse_version_orders():
    assert _parse_version("0.1.5") < _parse_version("0.1.6")
    assert _parse_version("0.1.10") > _parse_version("0.1.6")
    assert _parse_version("v0.2.0") > _parse_version("0.1.99")
