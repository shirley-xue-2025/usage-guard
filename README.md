# usage-guard

[![test](https://github.com/shirley-xue-2025/usage-guard/actions/workflows/test.yml/badge.svg)](https://github.com/shirley-xue-2025/usage-guard/actions/workflows/test.yml)

Opt-in proactive **5-hour usage guard** for long Claude Code sessions (macOS — Desktop Code tab and CLI).

Arm with `/usage-guard` before long batch, subagent, or overnight work — especially when the shared window is already partly used. An external daemon reads your usage (zero session tokens), sets `PAUSE` before the wall, sends macOS notifications, and you resume with `/usage-guard resume` after reset — without chat reminders that get queued behind subagents.

## Who is this for?

- **Long Claude Code sessions** that burn the **5-hour window** quickly (batch jobs, subagents, `/loop`, brain + code multi-session arcs)
- Work that starts when usage is **already high** — arm gives account-level visibility, not just this chat's view
- **Subagent / batch** work where mid-session chat messages stay **queued**
- You want to **pause near 90%** and avoid **extra usage wallet** charges at 100%
- **macOS** — Claude Desktop **Code** tab or Claude Code **CLI**
- You can arm once per session (`/usage-guard`) — no per-project setup

> Also used on heavy model runs (e.g. Fable when available). Same 5-hour wall either way.

> **Proactive vs reactive:** [claude-auto-retry](https://github.com/cheapestinference/claude-auto-retry) resumes *after* you hit the wall. usage-guard tries to pause *before* it.

## Why this exists

On long runs, chat messages queue while subagents work — so "stop at 90%" reminders never land in time. Hitting 100% can burn **extra usage wallet**. Stop buttons may not fully halt subagents. Each chat only sees its own usage; the daemon reads the **account-level 5-hour window** (same as Desktop Settings), so a session that "looks" fine at 58% can already be at 94% shared. This tool uses an **external control file + upfront session contract** instead of mid-run chat.

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

### Updating

> **Active development** — we ship fixes frequently from real session dogfood.

```bash
cd usage-guard          # your clone
git pull
./install.sh            # refreshes skill + CLI (git pull alone is not enough)
usage-guard doctor      # checks credentials + shows update notice if available
```

`doctor` compares your installed version to the latest GitHub release (cached 24h). Set `USAGE_GUARD_NO_UPDATE_CHECK=1` to skip.

### One-time: enable usage reads (Desktop-only users)

OAuth tokens may not exist until Claude Code CLI login:

```bash
npm i -g @anthropic-ai/claude-code
claude login
usage-guard doctor   # expect ✓ Usage API
```

See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Use

### Desktop Code tab

1. Open your project in the **Code** tab
2. Run: `/usage-guard your long task description` (type manually if it does not appear in the slash picker)
3. Approve the arm script when prompted — arm waits for the first usage poll before returning
4. Let it run — watch Terminal: `usage-guard status`

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports: use the [issue template](https://github.com/shirley-xue-2025/usage-guard/issues/new/choose).

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 Shirley Xue.
