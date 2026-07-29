"""usage-guard CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from usage_guard.control import (
    apply_usage_telemetry,
    apply_wait_schedule,
    default_checkpoint,
    default_control,
    ensure_dirs,
    enrich_time_fields,
    merge_done,
    new_session_id,
    read_checkpoint,
    read_control,
    checkpoint_session_id,
    session_dir,
    write_checkpoint,
    write_control,
)
from usage_guard.daemon import stop_daemon
from usage_guard import launchd as launchd_mod
from usage_guard.paths import (
    CONTROL_PATH,
    GUARD_DIR,
    LAUNCHD_LABEL,
    LAUNCHD_PLIST_PATH,
    LOG_PATH,
    PID_PATH,
)
from usage_guard.update_check import check_for_update, print_update_notice
from usage_guard.usage_fetch import UsageFetchError, doctor, format_extra_usage, get_usage


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python() -> str:
    return sys.executable


def _daemon_module() -> list[str]:
    return [_python(), "-m", "usage_guard.daemon"]


def _daemon_alive() -> bool:
    if not PID_PATH.exists():
        return False
    try:
        pid = int(PID_PATH.read_text(encoding="utf-8").strip())
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _start_daemon(session_id: str, *, mock_percent: float | None = None) -> str:
    """Start daemon via LaunchAgent when installed; else legacy Popen.

    Returns ``launchd`` or ``popen``.
    """
    if (
        mock_percent is None
        and launchd_mod.launchd_supported()
        and LAUNCHD_PLIST_PATH.exists()
        and launchd_mod.kickstart(kill=True)
    ):
        return "launchd"
    daemon_cmd = _daemon_module() + ["--session-id", session_id]
    if mock_percent is not None:
        daemon_cmd += ["--mock-percent", str(mock_percent)]
    log_handle = open(LOG_PATH, "a", encoding="utf-8")
    subprocess.Popen(
        daemon_cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(_repo_root()),
    )
    return "popen"


def wait_for_first_poll(*, timeout: float = 45.0, interval: float = 0.5) -> bool:
    """Block until daemon writes first usage percent, or timeout."""
    deadline = time.monotonic() + timeout
    pid_grace_until = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        control = read_control()
        if control.get("five_hour_percent") is not None:
            return True
        if time.monotonic() > pid_grace_until and not _daemon_alive():
            return False
        time.sleep(interval)
    return False


def cmd_doctor(_: argparse.Namespace) -> int:
    from usage_guard import __version__

    print(f"usage-guard v{__version__}")
    rc = doctor()
    print_update_notice(check_for_update())
    return rc


def _arm_status_warnings(prior: dict, *, prior_daemon_alive: bool) -> str | None:
    if prior.get("armed") and prior_daemon_alive:
        return None
    if prior.get("armed") and not prior_daemon_alive:
        return (
            "Guard was armed but daemon was not running — re-armed fresh. "
            "With LaunchAgent KeepAlive, crashes auto-restart; "
            "re-arm after disarm, logout without agent, or a clean exit."
        )
    if not prior.get("armed"):
        return (
            "Guard was not armed (IDLE/disarmed) — started fresh. "
            "Re-arm at the start of every sitting. "
            "Use /usage-guard resume to continue a paused task from checkpoint."
        )
    return None


def _merge_active_session_ids(prior: dict, session_id: str) -> list[str]:
    active = list(prior.get("active_session_ids") or [])
    for sid in (prior.get("session_id"), session_id):
        if sid and sid not in active:
            active.append(sid)
    return active


def cmd_arm(args: argparse.Namespace) -> int:
    ensure_dirs()
    prior = read_control()
    prior_daemon_alive = _daemon_alive()
    task = args.task or ""

    if args.join:
        if not prior_daemon_alive:
            print(
                "error: --join requires a running daemon; arm normally first",
                file=sys.stderr,
            )
            return 1
        control = read_control()
        sitting_id = args.session_id or new_session_id()
        checkpoint = read_checkpoint(sitting_id) or default_checkpoint(task)
        if task and not checkpoint.get("task"):
            checkpoint["task"] = task
        write_checkpoint(sitting_id, checkpoint)
        control["active_session_ids"] = _merge_active_session_ids(control, sitting_id)
        control["sitting_session_id"] = sitting_id
        write_control(control)
        enrich_time_fields(control)
        print(
            json.dumps(
                {
                    "joined": True,
                    "primary_session_id": control.get("session_id"),
                    "sitting_session_id": sitting_id,
                    "checkpoint_writes_target": sitting_id,
                    "active_session_ids": control.get("active_session_ids"),
                    "five_hour_percent": control.get("five_hour_percent"),
                    "five_hour_reset_local": control.get("five_hour_reset_local"),
                    "state": control.get("state"),
                    "guidance": (
                        "checkpoint.sh (no --session-id) now writes to sitting_session_id "
                        "until the next arm or join."
                    ),
                },
                indent=2,
            )
        )
        return 0

    session_id = args.session_id or new_session_id()

    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            if not args.force:
                control = read_control()
                enrich_time_fields(control)
                payload: dict = {
                    "already_armed": True,
                    "action": "proceed",
                    "guidance": (
                        "Daemon already running from a prior sitting. "
                        "Same arc, new sitting: join.sh --task 'label' "
                        "(checkpoints target sitting_session_id automatically). "
                        "Do not use --force unless intentionally restarting."
                    ),
                    "session_id": control.get("session_id"),
                    "sitting_session_id": control.get("sitting_session_id"),
                    "checkpoint_writes_target": checkpoint_session_id(control),
                    "active_session_ids": control.get("active_session_ids"),
                    "armed": control.get("armed"),
                    "daemon_alive": True,
                    "five_hour_percent": control.get("five_hour_percent"),
                    "five_hour_reset_local": control.get("five_hour_reset_local"),
                    "seconds_until_five_hour_reset": control.get(
                        "seconds_until_five_hour_reset"
                    ),
                    "awaiting_post_reset_poll": control.get(
                        "awaiting_post_reset_poll"
                    ),
                    "percent_note": control.get("percent_note"),
                    "state": control.get("state"),
                }
                if task:
                    payload["task_ignored"] = True
                    payload["task_note"] = (
                        "Task label not set on already-armed daemon. "
                        "Run join.sh with --task instead."
                    )
                print(json.dumps(payload, indent=2))
                return 0
        except OSError:
            PID_PATH.unlink(missing_ok=True)
        stop_daemon()

    checkpoint = default_checkpoint(task)
    write_checkpoint(session_id, checkpoint)

    control = default_control(session_id)
    control.update(
        {
            "armed": True,
            "state": "RUN",
            "phase": "waiting_first_poll",
            "session_id": session_id,
            "sitting_session_id": session_id,
            "active_session_ids": _merge_active_session_ids(prior, session_id),
            "note": "armed by CLI; waiting for first usage poll",
        }
    )
    write_control(control)

    start_via = _start_daemon(session_id, mock_percent=args.mock_percent)

    (session_dir(session_id) / "armed_at").write_text(
        datetime.now(timezone.utc).isoformat(),
        encoding="utf-8",
    )

    result: dict = {
        "session_id": session_id,
        "control_path": str(CONTROL_PATH),
        "daemon_start": start_via,
        "prior_armed": bool(prior.get("armed")),
        "prior_daemon_alive": prior_daemon_alive,
    }
    warning = _arm_status_warnings(prior, prior_daemon_alive=prior_daemon_alive)
    if warning:
        result["warning"] = warning

    if args.wait:
        if wait_for_first_poll(timeout=args.wait_timeout):
            control = read_control()
            result["first_poll"] = True
            result["five_hour_percent"] = control.get("five_hour_percent")
            result["five_hour_resets_at"] = control.get("five_hour_resets_at")
            result["five_hour_reset_local"] = control.get("five_hour_reset_local")
            result["seconds_until_five_hour_reset"] = control.get(
                "seconds_until_five_hour_reset"
            )
            result["five_hour_reset_pending"] = control.get("five_hour_reset_pending")
            result["phase"] = control.get("phase")
            result["active_session_ids"] = control.get("active_session_ids")
        else:
            control = read_control()
            result["first_poll"] = False
            result["phase"] = control.get("phase")
            if not _daemon_alive():
                print(
                    "error: daemon exited before first poll — check ~/.usage-guard/daemon.log",
                    file=sys.stderr,
                )
                return 1
            result["note"] = (
                f"first poll not received within {args.wait_timeout}s; "
                "daemon may still be warming up"
            )

    print(json.dumps(result, indent=2))
    return 0


def cmd_disarm(_: argparse.Namespace) -> int:
    control = read_control()
    control["armed"] = False
    control["state"] = "IDLE"
    control["phase"] = "idle"
    control["note"] = "disarmed by user"
    write_control(control)
    stop_daemon()
    print("disarmed")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    control = read_control()
    enrich_time_fields(control)
    session_id = control.get("session_id")
    target_id = checkpoint_session_id(control)
    checkpoint = read_checkpoint(target_id) if target_id else None

    print("usage-guard status")
    print("─" * 40)
    print(f"armed:   {control.get('armed')}")
    if control.get("telemetry_lost"):
        print("alert:   telemetry_lost — API returned no 5h %; state is UNKNOWN")
    if control.get("stale"):
        print(
            f"alert:   stale ({control.get('stale_reason')}) — "
            "past valid_until; treat as UNKNOWN"
        )
    print(f"state:   {control.get('state')} ({control.get('phase')})")
    if control.get("effective_state") and control.get("effective_state") != control.get(
        "state"
    ):
        print(f"obey:    {control.get('effective_state')} (effective_state)")
    if control.get("valid_until_local") or control.get("valid_until"):
        print(f"fresh:   until {control.get('valid_until_local') or control.get('valid_until')}")
    if control.get("pause_reason"):
        print(f"limit:   paused for {control.get('pause_reason')}")
    print(f"5h:      {control.get('five_hour_percent')}%")
    weekly = control.get("weekly_percent")
    if weekly is not None:
        weekly_local = control.get("weekly_reset_local")
        weekly_in = control.get("seconds_until_weekly_reset")
        line = f"weekly:  {weekly}%"
        if weekly_local and weekly_in is not None:
            when = f"in {weekly_in // 60}m" if weekly_in > 0 else "passed"
            line += f"  ({weekly_local}, {when})"
        print(line)
    extra = format_extra_usage(
        {
            "extraEnabled": control.get("extra_enabled"),
            "extraUsedCredits": control.get("extra_used_credits"),
            "extraMonthlyLimit": control.get("extra_monthly_limit"),
            "extraUtilization": control.get("extra_utilization"),
            "extraCurrency": control.get("extra_currency"),
        }
    )
    if extra:
        print(f"extra:   {extra}")
    resets_local = control.get("five_hour_reset_local")
    resets_in = control.get("seconds_until_five_hour_reset")
    if resets_local and resets_in is not None:
        when = f"in {resets_in // 60}m" if resets_in > 0 else "passed"
        print(f"resets:  {resets_local} ({when})")
    else:
        print(f"resets:  {control.get('five_hour_resets_at')}")
    print(f"resume:  {control.get('resume_at_local') or control.get('resume_at')}")
    print(f"reset:   {control.get('last_reset_at')}")
    sleep_local = control.get("sleep_until_local")
    sleep_in = control.get("seconds_until_sleep_until")
    if sleep_local and sleep_in is not None:
        print(f"sleep:   {sleep_local} (in {sleep_in // 60}m)")
    elif control.get("sleep_until"):
        print(f"sleep:   {control.get('sleep_until')}")
    print(f"loop:    every {control.get('session_check_seconds')}s (/loop hint)")
    print(f"session: {session_id} (primary)")
    sitting = control.get("sitting_session_id")
    if sitting and sitting != session_id:
        print(f"sitting: {sitting} (checkpoint target)")
    elif target_id:
        print(f"sitting: {target_id} (checkpoint target)")
    active = control.get("active_session_ids") or []
    if active:
        print(f"sessions:{', '.join(active)}")
    if checkpoint:
        done = len(checkpoint.get("done") or [])
        print(f"task:    {checkpoint.get('task') or '(none)'}")
        print(f"done:    {done} items")
        print(f"next:    {checkpoint.get('next')}")
    if PID_PATH.exists():
        print(f"daemon:  pid {PID_PATH.read_text(encoding='utf-8').strip()}")
    else:
        print("daemon:  not running")
    if launchd_mod.launchd_supported() and LAUNCHD_PLIST_PATH.exists():
        print(
            f"launchd: {LAUNCHD_LABEL} "
            f"({'loaded' if launchd_mod.is_loaded() else 'plist present, not loaded'})"
        )
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    control = read_control()
    session_id = checkpoint_session_id(control, args.session_id)
    if not session_id:
        print("error: no session_id (arm first or pass --session-id)", file=sys.stderr)
        return 1

    checkpoint = read_checkpoint(session_id) or default_checkpoint()

    if args.json:
        try:
            updates = json.loads(args.json)
        except json.JSONDecodeError as exc:
            print(f"error: invalid --json: {exc}", file=sys.stderr)
            return 1
        if not isinstance(updates, dict):
            print("error: --json must be an object", file=sys.stderr)
            return 1
        if "done" in updates:
            checkpoint["done"] = merge_done(checkpoint.get("done"), updates["done"])
        if "next" in updates:
            checkpoint["next"] = updates["next"]
        if "note" in updates:
            checkpoint["note"] = updates["note"]
        if "task" in updates:
            checkpoint["task"] = updates["task"]
    else:
        if args.done:
            checkpoint["done"] = merge_done(checkpoint.get("done"), args.done)
        if args.next is not None:
            checkpoint["next"] = args.next
        if args.note is not None:
            checkpoint["note"] = args.note
        if args.task is not None:
            checkpoint["task"] = args.task

    write_checkpoint(session_id, checkpoint)
    if args.quiet:
        done = checkpoint.get("done") or []
        last_done = done[-1] if done else None
        print(
            f"checkpoint saved: session={session_id} "
            f"done={last_done!r} next={checkpoint.get('next')!r}"
        )
    else:
        print(json.dumps({"session_id": session_id, "checkpoint": checkpoint}, indent=2))
    return 0


def cmd_poll(_: argparse.Namespace) -> int:
    """One-shot usage poll (for skill/testing)."""
    try:
        usage = get_usage()
        control = read_control()
        apply_usage_telemetry(control, usage)
        write_control(control)
        print(json.dumps(usage, indent=2))
        return 0
    except UsageFetchError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="usage-guard")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="Check credentials and usage API")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("arm", help="Arm guard and start daemon")
    p.add_argument("--session-id")
    p.add_argument("--task", default="")
    p.add_argument("--force", action="store_true")
    p.add_argument("--mock-percent", type=float)
    p.add_argument("--wait", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--wait-timeout", type=float, default=45.0)
    p.add_argument(
        "--join",
        action="store_true",
        help="Register this sitting's checkpoint without restarting daemon",
    )
    p.set_defaults(func=cmd_arm)

    p = sub.add_parser("checkpoint", help="Update session checkpoint (atomic merge)")
    p.add_argument("--session-id")
    p.add_argument("--done", action="append", default=[])
    p.add_argument("--next")
    p.add_argument("--note")
    p.add_argument("--task")
    p.add_argument("--json", help='JSON object, e.g. {"done":["item"],"next":"..."}')
    p.add_argument("--quiet", "-q", action="store_true", help="One-line confirmation")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("disarm", help="Stop daemon and disarm")
    p.set_defaults(func=cmd_disarm)

    p = sub.add_parser("status", help="Show guard status and checkpoint")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("poll", help="One-shot usage fetch")
    p.set_defaults(func=cmd_poll)

    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_dirs()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
