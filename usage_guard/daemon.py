"""Background usage polling daemon."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from datetime import datetime, timezone

from usage_guard.control import (
    apply_usage_telemetry,
    apply_wait_schedule,
    apply_telemetry_health,
    can_resume,
    default_control,
    effective_poll_percent,
    ensure_dirs,
    limit_hits,
    limits_config,
    load_config,
    now_iso,
    pause_note,
    pause_reason_from_hits,
    poll_interval_seconds,
    read_control,
    resume_at_for_pause,
    seconds_until_reset,
    write_control,
)
from usage_guard.notify import notify
from usage_guard.paths import LOG_PATH, PID_PATH
from usage_guard.usage_fetch import UsageFetchError, get_usage


def log(msg: str) -> None:
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line)
    except Exception:
        pass


def _notify_pause(control: dict, config: dict, reason: str | None) -> None:
    limits = limits_config(config)
    fh = control.get("five_hour_percent")
    wk = control.get("weekly_percent")
    if reason == "weekly":
        notify(
            "usage-guard",
            f"PAUSE at {wk:.0f}% weekly — finish current unit, do not start new subagents.",
        )
    elif reason == "both":
        notify(
            "usage-guard",
            f"PAUSE at {fh:.0f}% 5h and {wk:.0f}% weekly — finish unit, no new subagents.",
        )
    else:
        notify(
            "usage-guard",
            f"PAUSE at {fh:.0f}% — finish current unit, do not start new subagents.",
        )


def _notify_resume(control: dict, config: dict) -> None:
    limits = limits_config(config)
    parts: list[str] = []
    fh = control.get("five_hour_percent")
    wk = control.get("weekly_percent")
    if fh is not None:
        parts.append(f"5h {fh:.0f}%")
    if limits["weekly_enabled"] and wk is not None:
        parts.append(f"weekly {wk:.0f}%")
    summary = ", ".join(parts) if parts else "limits clear"
    notify("usage-guard", f"RUN again ({summary}) — you may resume work.")


def update_control_from_usage(
    control: dict,
    usage: dict,
    *,
    config: dict,
) -> dict:
    limits = limits_config(config)

    apply_usage_telemetry(control, usage)
    fh = control.get("five_hour_percent")
    hits = limit_hits(control, config)
    reason = pause_reason_from_hits(hits)

    if hits["any"]:
        if control.get("state") != "COOLDOWN":
            entering_pause = control.get("state") not in {"PAUSE", "COOLDOWN"}
            control["state"] = "PAUSE"
            control["phase"] = "pause"
            control["pause_reason"] = reason
            control["resume_at"] = resume_at_for_pause(control, hits)
            control["note"] = pause_note(reason, control, config)
            if entering_pause:
                _notify_pause(control, config, reason)
    elif control.get("state") == "PAUSE" and can_resume(control, config):
        control["state"] = "RUN"
        control["phase"] = "normal"
        control["resume_at"] = None
        control["pause_reason"] = None
        control["last_reset_at"] = now_iso()
        control["note"] = "usage dropped below threshold"
        _notify_resume(control, config)
    elif control.get("state") not in {"PAUSE", "COOLDOWN"} and can_resume(control, config):
        control["state"] = "RUN"
        control["phase"] = "normal"
        control["resume_at"] = None
        control["pause_reason"] = None
        control["note"] = ""

    if (
        fh is not None
        and fh >= limits["five_hour_warn"]
        and fh < limits["five_hour_pause"]
        and not control.get("warned_at_85")
    ):
        control["warned_at_85"] = True
        notify(
            "usage-guard",
            f"Warning: {fh:.0f}% of 5-hour window — avoid starting long subagent batches.",
        )

    wk = control.get("weekly_percent")
    if (
        limits["weekly_enabled"]
        and wk is not None
        and wk >= limits["weekly_warn"]
        and wk < limits["weekly_pause"]
        and not control.get("warned_at_weekly")
    ):
        control["warned_at_weekly"] = True
        notify(
            "usage-guard",
            f"Warning: {wk:.0f}% of weekly limit — avoid starting long subagent batches.",
        )

    apply_wait_schedule(control, margin=config["cooldown_margin_seconds"], config=config)

    effective = effective_poll_percent(control, config)
    wait = poll_interval_seconds(effective)
    if wait:
        control["daemon_next_poll_at"] = datetime.now(timezone.utc).timestamp() + wait
    if apply_telemetry_health(control, fh):
        notify(
            "usage-guard",
            "Blind — no 5h usage data. Run claude login or usage-guard doctor.",
        )
    return control


def run_daemon(session_id: str, *, mock_percent: float | None = None) -> int:
    ensure_dirs()
    config = load_config()
    control = read_control()
    if not control.get("armed"):
        control = default_control(session_id)
        control["armed"] = True
        control["state"] = "RUN"
        control["phase"] = "armed"
        control["session_id"] = session_id
        write_control(control)

    log(f"daemon start session={session_id} mock={mock_percent}")

    while True:
        control = read_control()
        if not control.get("armed"):
            log("disarmed; exiting")
            return 0

        if control.get("state") == "COOLDOWN":
            sleep_for = seconds_until_reset(
                control.get("resume_at")
                or control.get("five_hour_resets_at")
                or control.get("weekly_resets_at"),
                config["cooldown_margin_seconds"],
            )
            if sleep_for is None:
                sleep_for = 30 * 60
            log(f"cooldown sleep {sleep_for}s")
            time.sleep(min(sleep_for, 59 * 60))
            try:
                usage = get_usage(mock_percent=mock_percent)
                control = update_control_from_usage(control, usage, config=config)
                if control.get("state") == "PAUSE":
                    control["state"] = "COOLDOWN"
                    control["phase"] = "cooldown"
                    apply_wait_schedule(
                        control,
                        margin=config["cooldown_margin_seconds"],
                        config=config,
                    )
                elif can_resume(control, config):
                    control["state"] = "RUN"
                    control["phase"] = "normal"
                    control["last_reset_at"] = now_iso()
                    control["note"] = "cooldown complete"
                    control["pause_reason"] = None
                    control["resume_at"] = None
                    notify(
                        "usage-guard",
                        "Usage window reset — run /usage-guard resume if needed.",
                    )
                write_control(control)
            except UsageFetchError as exc:
                log(f"cooldown usage error: {exc}")
            continue

        try:
            usage = get_usage(mock_percent=mock_percent)
            control = update_control_from_usage(control, usage, config=config)
            if control.get("state") == "PAUSE":
                control["state"] = "COOLDOWN"
                control["phase"] = "cooldown"
                apply_wait_schedule(
                    control,
                    margin=config["cooldown_margin_seconds"],
                    config=config,
                )
            write_control(control)
            extra_used = usage.get("extraUsedCredits")
            extra_note = f" extra_used={extra_used}" if extra_used is not None else ""
            weekly = usage.get("weeklyPercent")
            weekly_note = f" weekly={weekly}" if weekly is not None else ""
            log(
                f"poll percent={usage.get('fiveHourPercent')}{weekly_note} "
                f"state={control.get('state')}{extra_note}"
            )
        except UsageFetchError as exc:
            log(f"poll error (fail-open, keep prior control): {exc}")

        control = read_control()
        if control.get("state") == "COOLDOWN":
            continue

        wait = poll_interval_seconds(effective_poll_percent(control, config))
        if wait <= 0:
            wait = 60
        time.sleep(wait)


def write_pid() -> None:
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")


def stop_daemon() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGTERM)
        PID_PATH.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--mock-percent", type=float, default=None)
    args = parser.parse_args(argv)

    write_pid()

    def handle_sigterm(_signum, _frame):
        log("received SIGTERM")
        PID_PATH.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)
    return run_daemon(args.session_id, mock_percent=args.mock_percent)


if __name__ == "__main__":
    raise SystemExit(main())
