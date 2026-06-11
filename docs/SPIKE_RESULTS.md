# Spike results (Mac, Claude Desktop Code user)

Date: 2026-06-12  
Machine: macOS, Claude Desktop Code (no `claude` CLI in PATH)

## Spike 1: OAuth usage API without browser

| Check | Result |
|-------|--------|
| Keychain `Claude Code-credentials` | Present, but **mcpOAuth only** — no `claudeAiOauth` / `sk-ant-oat` token |
| All 59 `Claude Code-credentials-*` entries | Same — mcpOAuth only |
| `~/.claude/.credentials.json` | Missing |
| Desktop session `.credentials.json` files | mcpOAuth only |
| `cu --json` (ai-usage-monitors) | **Failed**: "No Claude Code credentials found" |
| `~/.claude.json` `oauthAccount` | Account metadata present (email, tier) — **no access token** |

**Conclusion:** Desktop Code can run sessions, but **usage reads need a one-time OAuth setup** via Claude Code CLI login (or another path that populates `claudeAiOauth`). The daemon code supports this; `usage-guard doctor` explains the fix.

**Recommended user setup (one time):**

```bash
npm i -g @anthropic-ai/claude-code
claude login
usage-guard doctor   # should show ✓ Usage API
```

Alternative: `npm i -g github:minhvoio/ai-usage-monitors` after login (`cu --json`).

## Spike 2: `/loop` wake interval

Per [Claude Code scheduled tasks docs](https://code.claude.com/docs/en/scheduled-tasks):

- `/loop` minimum interval: **1 minute**
- Dynamic mode: **1 minute – 1 hour**
- **No 59-minute hard cap** on daemon sleep; session loop should cap at 59m and chain for longer cooldowns

## Spike 3: Mock mode for development

Works without OAuth:

```bash
cd usage-guard
PYTHONPATH=. python3 -m usage_guard arm --mock-percent 88 --force
PYTHONPATH=. python3 -m usage_guard status
```

## Spike 4–6 (session behavior)

Requires live Fable session with armed guard — manual test checklist in README.
