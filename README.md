# usage-guard

Opt-in proactive **5-hour usage guard** for long Claude Code sessions (macOS — Desktop Code tab and CLI).

Arm with `/usage-guard` before Fable-scale or batch work. An external daemon reads your usage (zero session tokens), sets `PAUSE` before the wall, sends macOS notifications, and you resume with `/usage-guard resume` after reset — without chat reminders that get queued behind subagents.

## Why this exists

On long Fable runs, chat messages queue while subagents work — so "stop at 90%" reminders never land in time. Hitting 100% can burn **extra usage wallet**. Stop buttons may not fully halt subagents. This tool uses an **external control file + upfront session contract** instead of mid-run chat.

## How it works

```
/usage-guard  →  arm daemon  →  ~/.usage-guard/control.json
                                      ↑
Session (cooperative)  ←── read state at safe checkpoints only
  - before each subagent batch
  - after each unit completes
  - on /loop guard ticks
```

| Layer | Role | Tokens |
|-------|------|--------|
| **Daemon** | OAuth usage poll, adaptive schedule, notifications | 0 |
| **Skill** | Arm, checkpoint rules, `/loop` timetable | Minimal reads |

## Install (macOS)

```bash
cd usage-guard
chmod +x install.sh
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.zshrc if needed
usage-guard doctor
```

### One-time: enable usage reads (Desktop-only users)

Spike on Desktop-only machines: OAuth tokens may not exist until Claude Code CLI login:

```bash
npm i -g @anthropic-ai/claude-code
claude login
usage-guard doctor   # expect ✓ Usage API
```

See [docs/SPIKE_RESULTS.md](docs/SPIKE_RESULTS.md).

## Use

### Desktop Code tab

1. Open your project in the **Code** tab
2. Optional: select **Fable** model for heavy work
3. Run: `/usage-guard your long task description`
4. Approve the arm script when prompted
5. Let it run — watch Terminal: `usage-guard status`

### After reset (new session OK)

```
/usage-guard resume
```

### CLI

Same `/usage-guard` skill after install (shared `~/.claude/skills/`).

## Commands

```bash
usage-guard doctor          # credentials + usage API check
usage-guard arm             # start daemon + session
usage-guard status          # state, %, checkpoint
usage-guard disarm          # stop daemon
usage-guard poll            # one-shot usage fetch
```

### Mock mode (no OAuth)

```bash
PYTHONPATH=. python3 -m usage_guard arm --mock-percent 91 --force
PYTHONPATH=. python3 -m usage_guard status
```

## Configuration

Optional `~/.usage-guard/config.json`:

```json
{
  "threshold_pause": 90,
  "threshold_warn": 85,
  "cooldown_margin_seconds": 60
}
```

## Honest limits

- **Cooperative** — session must follow skill rules; we brief up front, not mid-run inject
- **Cannot force-stop** a running subagent; prevents *new* work after PAUSE
- **Checkpoints** — progress safety depends on frequent writes to `checkpoint.json`
- **Force quit** — use `/usage-guard resume` in a new session; checkpoint is on disk
- **Extra wallet at 100%** — guard aims to pause at 90%; cannot stop Desktop if session ignores PAUSE

## Complements

- [claude-auto-retry](https://github.com/cheapestinference/claude-auto-retry) — reactive resume after hard limit (optional belt-and-suspenders)
- [ai-usage-monitors](https://github.com/minhvoio/ai-usage-monitors) `cu` — usage reading (MIT, credited in code)

## License

MIT
