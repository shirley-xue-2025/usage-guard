"""usage-guard CLI entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from usage_guard.control import (
    default_checkpoint,
    default_control,
    ensure_dirs,
    new_session_id,
    read_checkpoint,
    read_control,
    session_dir,
    write_checkpoint,
    write_control,
)
from usage_guard.daemon import stop_daemon
from usage_guard.paths import CONTROL_PATH, GUARD_DIR, LOG_PATH, PID_PATH
from usage_guard.usage_fetch import UsageFetchError, doctor, get_usage


def _python() -> str:
    return sys.executable


def _daemon_module() -> list[str]:
    return [_python(), "-m", "usage_guard.daemon"]


def cmd_doctor(_: argparse.Namespace) -> int:
    return doctor()


def cmd_arm(args: argparse.Namespace) -> int:
    ensure_dirs()
    session_id = args.session_id or new_session_id()
    task = args.task or ""

    if PID_PATH.exists():
        try:
            pid = int(PID_PATH.read_text(encoding="utf-8").strip())
            os.kill(pid, 0)
            if not args.force:
                print(f"Daemon already running (pid {pid}). Use --force to restart.")
                print(f"session_id={read_control().get('session_id')}")
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
            "phase": "armed",
            "session_id": session_id,
            "note": "armed by CLI",
        }
    )
    write_control(control)

    daemon_cmd = _daemon_module() + ["--session-id", session_id]
    if args.mock_percent is not None:
        daemon_cmd += ["--mock-percent", str(args.mock_percent)]

    log_handle = open(LOG_PATH, "a", encoding="utf-8")
    subprocess.Popen(
        daemon_cmd,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )

    (session_dir(session_id) / "armed_at").write_text(
        datetime.now(timezone.utc).isoformat(),
        encoding="utf-8",
    )

    print(json.dumps({"session_id": session_id, "control_path": str(CONTROL_PATH)}, indent=2))
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
    session_id = control.get("session_id")
    checkpoint = read_checkpoint(session_id) if session_id else None

    print("usage-guard status")
    print("─" * 40)
    print(f"armed:   {control.get('armed')}")
    print(f"state:   {control.get('state')} ({control.get('phase')})")
    print(f"5h:      {control.get('five_hour_percent')}%")
    print(f"resets:  {control.get('five_hour_resets_at')}")
    print(f"resume:  {control.get('resume_at')}")
    print(f"check:   every {control.get('session_check_seconds')}s (session)")
    print(f"session: {session_id}")
    if checkpoint:
        done = len(checkpoint.get("done") or [])
        print(f"task:    {checkpoint.get('task') or '(none)'}")
        print(f"done:    {done} items")
        print(f"next:    {checkpoint.get('next')}")
    if PID_PATH.exists():
        print(f"daemon:  pid {PID_PATH.read_text(encoding='utf-8').strip()}")
    else:
        print("daemon:  not running")
    return 0


def cmd_poll(_: argparse.Namespace) -> int:
    """One-shot usage poll (for skill/testing)."""
    try:
        usage = get_usage()
        control = read_control()
        control["five_hour_percent"] = usage.get("fiveHourPercent")
        control["five_hour_resets_at"] = usage.get("fiveHourResetsAt")
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
    p.set_defaults(func=cmd_arm)

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
