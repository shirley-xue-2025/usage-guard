# Troubleshooting

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

`doctor` shows `⚠ connected but five_hour percent is null`. The daemon stays fail-open (`RUN`) but **cannot pause at 90%**. Common causes: expired OAuth token (`claude login`), API outage, or account type edge case.

After 3 null polls, control.json sets `telemetry_lost: true` and `phase: telemetry_lost`. Check Desktop usage manually until `poll` shows a real percent. Try `cu --json` fallback after installing [ai-usage-monitors](https://github.com/minhvoio/ai-usage-monitors).

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
