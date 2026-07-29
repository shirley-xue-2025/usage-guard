# Contributing to usage-guard

Thanks for helping improve usage-guard. This is a small macOS-focused tool; contributions that match that scope are especially welcome.

## Ways to contribute

- **Bug reports** — use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.yml) and include `usage-guard doctor` output
- **Documentation** — README clarity, Desktop/CLI screenshots, edge cases you hit with Fable
- **Code** — daemon reliability, credential discovery, clearer errors
- **Ideas** — open a [GitHub Discussion](https://github.com/shirley-xue-2025/usage-guard/discussions) or an issue labeled `idea`

## Scope (v0.x)

| In scope | Out of scope (for now) |
|----------|-------------------------|
| macOS + Claude Code Desktop/CLI | Windows/Linux |
| Proactive pause + checkpoint + resume | Force-stopping runaway subagents |
| OAuth usage reads (`usage-guard doctor`) | Codex / other providers |

## Development setup

```bash
git clone https://github.com/shirley-xue-2025/usage-guard.git
cd usage-guard
export PATH="$HOME/.local/bin:$PATH"
./install.sh          # optional: installs skill + CLI wrapper
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"

usage-guard doctor    # needs `claude login` for live usage
python3 -m pytest tests/ -q
bash scripts/check-public-clean.sh   # blocks Ring-2 / personal leaks
```

Enable the pre-push hook once per clone (recommended for maintainers):

```bash
git config core.hooksPath .githooks
```

The same clean check runs in CI on every push/PR.

### Mock mode (no OAuth)

```bash
PYTHONPATH=. python3 -m usage_guard arm --mock-percent 88 --force
PYTHONPATH=. python3 -m usage_guard status
PYTHONPATH=. python3 -m usage_guard disarm
```

## Pull requests

1. Fork and branch from `main` (`fix/...`, `feat/...`, `docs/...`)
2. Keep PRs focused — one concern per PR when possible
3. Run tests: `python3 -m pytest tests/ -q`
4. Update README if behavior or install steps change
5. Describe **what** and **why** in the PR body

We may squash-merge small PRs to keep history readable.

## Code style

- Python 3.10+ compatible stdlib-first (curl for API calls on macOS)
- Match existing module layout under `usage_guard/`
- Prefer clear errors over silent failures; document fail-open vs fail-closed behavior

## Community

Be respectful and constructive. This project is maintained in spare time — patience is appreciated.
