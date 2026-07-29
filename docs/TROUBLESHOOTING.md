# Troubleshooting

## `No module named usage_guard` when arming

`claude login` fixes **OAuth** only. This error means Python cannot import the `usage_guard` package — the CLI wrapper or skill fallback has a **stale or wrong `PYTHONPATH`**.

**Typical cause:** repo was moved or you have a new clone, but `~/.local/bin/usage-guard` still points at an old path from a previous `./install.sh`.

**What you should see after v0.1.11:** a clear message (`clone not found at …` or `Re-run ./install.sh`) instead of a raw `ModuleNotFoundError`.

**Fix:**

```bash
cd usage-guard    # your current clone
./install.sh
export PATH="$HOME/.local/bin:$PATH"
usage-guard doctor
```

**Verify:** `grep PYTHONPATH ~/.local/bin/usage-guard` should show your current clone's absolute path.

**Note:** `git pull` does not refresh the wrapper — run `./install.sh` after pulls (see README Updating).

**Weekly monitoring:** enable in `~/.usage-guard/config.json` with `"weekly_enabled": true`. Matches Desktop "All models" weekly bar, not per-model Sonnet limits.

---

## `/usage-guard` not in slash command picker

The skill sets `disable-model-invocation: true` so Claude does not auto-arm sessions. On some Desktop / Fable builds it may also be **hidden from the picker** — **type `/usage-guard` manually** anyway (autocomplete optional).

If the user asks you to "use usage-guard" without the slash command, the model should read `~/.claude/skills/usage-guard/SKILL.md` and run `arm.sh`.

Re-run `./install.sh` and restart Desktop if the skill folder is missing.

## Null `five_hour_percent` right after arm

Expected for a few seconds: `phase` is `waiting_first_poll`. `arm` blocks until the first poll (or ~45s timeout). If telemetry stays null, run `usage-guard status` — confirm `daemon: pid …` is shown. Check `~/.usage-guard/daemon.log`.

## `usage-guard doctor` fails: no OAuth credentials

Desktop Code can run sessions without the Claude Code CLI, but **usage reads** need OAuth tokens in Keychain or `~/.claude/.credentials.json`.

**Fix (one time):**

```bash
npm i -g @anthropic-ai/claude-code
claude login
usage-guard doctor
```

Alternative: install [`cu`](https://github.com/minhvoio/ai-usage-monitors) after login (`cu --json`).

## Usage API works but percent looks wrong

Compare `usage-guard poll` with Claude Desktop → Settings → Usage. Small differences can happen near window boundaries. If they diverge by more than ~5%, open an issue with both readings.

## Usage API returns null percent

`doctor` shows `⚠ connected but five_hour percent is null`. After 3 null polls, control.json sets `state: UNKNOWN`, `telemetry_lost: true`, and `phase: telemetry_lost`. You get a macOS notification at detection, then hourly (first few hours), then daily until recovery. Check Desktop usage manually until `poll` shows a real percent. Try `cu --json` fallback after installing [ai-usage-monitors](https://github.com/minhvoio/ai-usage-monitors).

## Daemon died quietly / control.json looks stuck

`./install.sh` installs a LaunchAgent (`io.usage-guard.daemon`) with KeepAlive so crashes restart automatically; a clean `disarm` stays down. Check:

```bash
launchctl print gui/$(id -u)/io.usage-guard.daemon
usage-guard status   # shows valid_until, stale, effective_state
```

If `stale: true` or `now > valid_until`, treat the file as `UNKNOWN` even when `state` says `RUN`.

## COOLDOWN wake-up did not fire

Session-scoped `/loop` and `CronCreate` tasks only fire while **Claude Code is running and idle** — closing the terminal stops them. Checkpoint is still safe; use `/usage-guard resume` after reset.

- **Session said "ping me when reset"?** Skill violation — schedule a wake (path A or B), not a passive wait.
- **Wake didn't fire?** Session-scoped timers need Claude Code **open and idle**; closing the terminal stops them. Esc clears a pending `/loop` wakeup.

## `/loop` and long cooldowns

- `/loop` minimum interval: **1 minute**; dynamic mode up to **~1 hour** per tick
- The daemon can sleep longer than 1 hour during cooldown
- In `COOLDOWN`, the skill should chain `/loop` checks (e.g. 59m) until `state` is `RUN` again

See [Claude Code scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks).

## Mock mode (development, no OAuth)

```bash
cd usage-guard
PYTHONPATH=. python3 -m usage_guard arm --mock-percent 88 --force
PYTHONPATH=. python3 -m usage_guard status
PYTHONPATH=. python3 -m usage_guard disarm
```
