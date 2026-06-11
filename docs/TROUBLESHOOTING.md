# Troubleshooting

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
