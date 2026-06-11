# usage-guard

[![test](https://github.com/shirley-xue-2025/usage-guard/actions/workflows/test.yml/badge.svg)](https://github.com/shirley-xue-2025/usage-guard/actions/workflows/test.yml)

Opt-in proactive **5-hour usage guard** for long Claude Code sessions (macOS — Desktop Code tab and CLI).

Arm with `/usage-guard` before Fable-scale or batch work. An external daemon reads your usage (zero session tokens), sets `PAUSE` before the wall, sends macOS notifications, and you resume with `/usage-guard resume` after reset — without chat reminders that get queued behind subagents.

## Who is this for?

- Long **Fable 5** or Opus sessions that burn the **5-hour window** quickly
- **Subagent / batch** work where mid-session chat messages stay **queued**
- You want to **pause near 90%** and avoid **extra usage wallet** charges at 100%
- **macOS** — Claude Desktop **Code** tab or Claude Code **CLI**
- You can arm once per session (`/usage-guard`) — no per-project setup

> **Proactive vs reactive:** [claude-auto-retry](https://github.com/cheapestinference/claude-auto-retry) resumes *after* you hit the wall. usage-guard tries to pause *before* it.

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
git clone https://github.com/shirley-xue-2025/usage-guard.git
cd usage-guard
chmod +x install.sh
./install.sh
export PATH="$HOME/.local/bin:$PATH"   # add to ~/.zshrc if needed
usage-guard doctor
```

### One-time: enable usage reads (Desktop-only users)

OAuth tokens may not exist until Claude Code CLI login:

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
cd usage-guard
PYTHONPATH=. python3 -m usage_guard arm --mock-percent 91 --force
PYTHONPATH=. python3 -m usage_guard status
PYTHONPATH=. python3 -m usage_guard disarm
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

## Disclaimer

**Not affiliated with Anthropic.** usage-guard is an independent community tool.

- Reads usage via the same **OAuth usage endpoint** used by tools like [`cu`](https://github.com/minhvoio/ai-usage-monitors) — this is **not** a documented public API and may change without notice.
- Pause/resume is **best-effort** and **cooperative**; it does not modify Claude Desktop or guarantee you avoid extra usage charges.
- You are responsible for how you use your Claude subscription.

## Related tools

| Tool | When to use |
|------|-------------|
| **usage-guard** (this repo) | Proactive pause ~90%, checkpoints, resume after reset |
| [claude-auto-retry](https://github.com/cheapestinference/claude-auto-retry) | Reactive auto-`continue` after limit message |
| [ai-usage-monitors](https://github.com/minhvoio/ai-usage-monitors) `cu` | Check current 5h % in terminal (no guard) |

Many people use **usage-guard + claude-auto-retry** together: pause early when possible; auto-continue if you still hit 100%.

## Demo

<!-- TODO: add a 30–60s screen recording (arm → status → macOS notification) and link it here -->

Screen recording welcome — see [docs/MANUAL_CHECKLIST.md](docs/MANUAL_CHECKLIST.md#issue-optional-demo-gif).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports: use the [issue template](https://github.com/shirley-xue-2025/usage-guard/issues/new/choose).

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Shirley Xue.
