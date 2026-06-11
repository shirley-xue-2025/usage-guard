#!/usr/bin/env python3
"""Read Claude Code OAuth usage without consuming session tokens.

Credential discovery adapted from ai-usage-monitors (MIT).
https://github.com/minhvoio/ai-usage-monitors
"""

from __future__ import annotations

import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from usage_guard.paths import CLAUDE_CREDENTIAL_PATHS, DESKTOP_CLAUDE_DIR

API_TIMEOUT_S = 10
KEYCHAIN_SVC = "Claude Code-credentials"
OAUTH_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


class UsageFetchError(Exception):
    pass


def _find_oauth_block(obj: Any) -> dict | None:
    if not isinstance(obj, dict):
        return None
    token = obj.get("accessToken", "")
    if isinstance(token, str) and token.startswith("sk-ant-oat"):
        return obj
    for value in obj.values():
        if isinstance(value, dict):
            found = _find_oauth_block(value)
            if found:
                return found
    return None


def _parse_credentials_blob(parsed: dict) -> dict | None:
    creds = parsed.get("claudeAiOauth")
    if isinstance(creds, dict) and creds.get("accessToken"):
        return {
            "accessToken": creds["accessToken"],
            "expiresAt": creds.get("expiresAt"),
            "refreshToken": creds.get("refreshToken"),
            "source": "file",
        }
    block = _find_oauth_block(parsed)
    if block:
        return {
            "accessToken": block["accessToken"],
            "expiresAt": block.get("expiresAt"),
            "refreshToken": block.get("refreshToken"),
            "source": "recursive",
        }
    return None


def read_keychain_credentials(service: str = KEYCHAIN_SVC) -> dict | None:
    if platform.system() != "Darwin":
        return None
    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s", service, "-w"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        raw = result.stdout.strip()
        if not raw:
            return None
        parsed = json.loads(raw)
        creds = _parse_credentials_blob(parsed)
        if creds:
            creds["source"] = f"keychain:{service}"
        return creds
    except Exception:
        return None


def read_credentials_file(path: Path) -> dict | None:
    try:
        if not path.exists():
            return None
        creds = _parse_credentials_blob(json.loads(path.read_text()))
        if creds:
            creds["source"] = str(path)
        return creds
    except Exception:
        return None


def list_keychain_credential_services() -> list[str]:
    if platform.system() != "Darwin":
        return []
    try:
        dump = subprocess.run(
            ["/usr/bin/security", "dump-keychain"],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout
        services = re.findall(
            r'"svce"<blob>="(Claude Code-credentials[^"]*)"',
            dump,
        )
        return sorted(set(services))
    except Exception:
        return []


def read_credentials() -> dict | None:
    """Best-effort credential discovery for Desktop + CLI on macOS."""
    if platform.system() == "Darwin":
        for service in list_keychain_credential_services():
            creds = read_keychain_credentials(service)
            if creds:
                return creds

    for path in CLAUDE_CREDENTIAL_PATHS:
        creds = read_credentials_file(path)
        if creds:
            return creds

    if DESKTOP_CLAUDE_DIR.exists():
        for path in DESKTOP_CLAUDE_DIR.rglob(".credentials.json"):
            creds = read_credentials_file(path)
            if creds:
                return creds

    return None


def is_token_expired(creds: dict) -> bool:
    exp = creds.get("expiresAt")
    if exp is None:
        return False
    return exp <= datetime.now(timezone.utc).timestamp() * 1000


def refresh_access_token(refresh_token: str) -> dict | None:
    body = (
        f"grant_type=refresh_token&refresh_token={refresh_token}"
        f"&client_id={OAUTH_CLIENT_ID}"
    )
    try:
        result = subprocess.run(
            [
                "curl",
                "-s",
                "--max-time",
                str(API_TIMEOUT_S),
                "-X",
                "POST",
                "https://platform.claude.com/v1/oauth/token",
                "-H",
                "Content-Type: application/x-www-form-urlencoded",
                "-d",
                body,
            ],
            capture_output=True,
            text=True,
            timeout=API_TIMEOUT_S + 2,
        )
        if result.returncode == 0 and result.stdout.strip():
            parsed = json.loads(result.stdout.strip())
            if parsed.get("access_token"):
                return {
                    "accessToken": parsed["access_token"],
                    "refreshToken": parsed.get("refresh_token", refresh_token),
                    "expiresAt": int(datetime.now(timezone.utc).timestamp() * 1000)
                    + parsed.get("expires_in", 3600) * 1000,
                }
    except Exception:
        pass
    return None


def fetch_usage_raw(access_token: str) -> dict:
    result = subprocess.run(
        [
            "curl",
            "-s",
            "--max-time",
            str(API_TIMEOUT_S),
            USAGE_URL,
            "-H",
            f"Authorization: Bearer {access_token}",
            "-H",
            "anthropic-beta: oauth-2025-04-20",
        ],
        capture_output=True,
        text=True,
        timeout=API_TIMEOUT_S + 2,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise UsageFetchError(f"usage API request failed: {result.stderr.strip()}")
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise UsageFetchError(f"usage API returned non-JSON: {result.stdout[:200]}") from exc


def clamp_pct(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return None


def parse_usage(raw: dict) -> dict:
    fh = raw.get("five_hour") or {}
    sd = raw.get("seven_day") or {}
    ex = raw.get("extra_usage") or {}
    return {
        "fiveHourPercent": clamp_pct(fh.get("utilization")),
        "fiveHourResetsAt": fh.get("resets_at"),
        "weeklyPercent": clamp_pct(sd.get("utilization")),
        "weeklyResetsAt": sd.get("resets_at"),
        "extraEnabled": ex.get("is_enabled"),
        "extraUsedCredits": ex.get("used_credits"),
    }


def fetch_usage_via_cu() -> dict:
    """Optional fallback if `cu` from ai-usage-monitors is installed."""
    result = subprocess.run(
        ["cu", "--json"],
        capture_output=True,
        text=True,
        timeout=API_TIMEOUT_S + 5,
    )
    if result.returncode != 0:
        raise UsageFetchError(result.stderr.strip() or "cu --json failed")
    return json.loads(result.stdout.strip())


def get_usage(*, mock_percent: float | None = None) -> dict:
    if mock_percent is not None:
        return {
            "fiveHourPercent": mock_percent,
            "fiveHourResetsAt": None,
            "weeklyPercent": None,
            "weeklyResetsAt": None,
            "extraEnabled": None,
            "extraUsedCredits": None,
            "source": "mock",
        }

    creds = read_credentials()
    if not creds:
        try:
            data = fetch_usage_via_cu()
            data["source"] = "cu"
            return data
        except Exception as cu_err:
            raise UsageFetchError(
                "No Claude OAuth credentials found for usage reads. "
                "Desktop Code users: install Claude Code CLI once and run `claude login`, "
                "or install `cu` from ai-usage-monitors after logging in. "
                f"cu fallback: {cu_err}"
            ) from cu_err

    if is_token_expired(creds) and creds.get("refreshToken"):
        refreshed = refresh_access_token(creds["refreshToken"])
        if refreshed:
            creds.update(refreshed)

    raw = fetch_usage_raw(creds["accessToken"])
    parsed = parse_usage(raw)
    parsed["source"] = creds.get("source", "oauth")
    return parsed


def doctor() -> int:
    print("usage-guard doctor")
    print("─" * 40)
    creds = read_credentials()
    if creds:
        print(f"✓ OAuth credentials: {creds.get('source')}")
        print(f"  token prefix: {creds['accessToken'][:20]}...")
    else:
        print("✗ OAuth credentials: not found")
        print("  Keychain entries checked:", len(list_keychain_credential_services()))
        print("  Fix: npm i -g @anthropic-ai/claude-code && claude login")
        print("  Or: npm i -g github:minhvoio/ai-usage-monitors  (after login)")

    try:
        usage = get_usage()
        print(f"✓ Usage API: five_hour={usage.get('fiveHourPercent')}%")
        if usage.get("fiveHourResetsAt"):
            print(f"  resets at: {usage['fiveHourResetsAt']}")
        return 0
    except UsageFetchError as exc:
        print(f"✗ Usage API: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(doctor())
