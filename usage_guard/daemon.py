"""Background usage polling daemon."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from datetime import datetime, timezone

from usage_guard.control import (
    apply_wait_schedule,
    apply_telemetry_health,
    default_control,
    ensure_dirs,
    load_config,
    now_iso,
    poll_interval_seconds,
    read_control,
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


def update_control_from_usage(
    control: dict,
    usage: dict,
    *,
    config: dict,
) -> dict:
    percent = usage.get("fiveHourPercent")
    resets_at = usage.get("fiveHourResetsAt")
    threshold = config["threshold_pause"]
    warn_threshold = config["threshold_warn"]

    control["five_hour_percent"] = percent
    control["five_hour_resets_at"] = resets_at

    if percent is not None and percent >= threshold:
        if control.get("state") != "COOLDOWN":
            control["state"] = "PAUSE"
            control["phase"] = "pause"
            control["resume_at"] = resets_at
            control["note"] = f"five_hour >= {threshold}%"
            notify(
                "usage-guard",
                f"PAUSE at {percent:.0f}% — finish current unit, do not start new subagents.",
            )
    elif control.get("state") == "PAUSE" and percent is not None and percent < threshold:
        control["state"] = "RUN"
        control["phase"] = "normal"
        control["resume_at"] = None
        control["last_reset_at"] = now_iso()
        control["note"] = "usage dropped below threshold"
        notify("usage-guard", f"RUN again at {percent:.0f}% — you may resume work.")
    elif control.get("state") not in {"PAUSE", "COOLDOWN"} and percent is not None:
        control["state"] = "RUN"
        control["phase"] = "normal"
        control["resume_at"] = None
        control["note"] = ""

    if (
        percent is not None
        and percent >= warn_threshold
        and percent < threshold
        and not control.get("warned_at_85")
    ):
        control["warned_at_85"] = True
        notify(
            "usage-guard",
            f"Warning: {percent:.0f}% of 5-hour window — avoid starting long subagent batches.",
        )

    apply_wait_schedule(control, margin=config["cooldown_margin_seconds"])

    wait = poll_interval_seconds(percent)
    if wait:
        control["daemon_next_poll_at"] = datetime.now(timezone.utc).timestamp() + wait
    if apply_telemetry_health(control, percent):
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
                control.get("resume_at") or control.get("five_hour_resets_at"),
                config["cooldown_margin_seconds"],
            )
            if sleep_for is None:
                sleep_for = 30 * 60
            log(f"cooldown sleep {sleep_for}s")
            time.sleep(min(sleep_for, 59 * 60))
            try:
                usage = get_usage(mock_percent=mock_percent)
                control = update_control_from_usage(control, usage, config=config)
                if control.get("state") != "COOLDOWN":
                    write_control(control)
                else:
                    control["state"] = "RUN"
                    control["phase"] = "normal"
                    control["last_reset_at"] = now_iso()
                    control["note"] = "cooldown complete"
                    write_control(control)
                    notify("usage-guard", "5-hour window reset — run /usage-guard resume if needed.")
            except UsageFetchError as exc:
                log(f"cooldown usage error: {exc}")
            continue

        try:
            usage = get_usage(mock_percent=mock_percent)
            control = update_control_from_usage(control, usage, config=config)
            if control.get("state") == "PAUSE":
                control["state"] = "COOLDOWN"
                control["phase"] = "cooldown"
                apply_wait_schedule(control, margin=config["cooldown_margin_seconds"])
            write_control(control)
            log(
                f"poll percent={usage.get('fiveHourPercent')} state={control.get('state')}"
            )
        except UsageFetchError as exc:
            log(f"poll error (fail-open, keep prior control): {exc}")

        control = read_control()
        if control.get("state") == "COOLDOWN":
            continue

        wait = poll_interval_seconds(control.get("five_hour_percent"))
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
