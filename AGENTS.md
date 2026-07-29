# Agent notes — usage-guard repo

## Before changing code

```bash
cd usage-guard   # this repo
export PYTHONPATH="$(pwd):${PYTHONPATH:-}"
python3 -m pytest tests/ -q
```

## Common setup failure

`No module named usage_guard` when running `/usage-guard` → run `./install.sh` from **this** clone (wrapper `PYTHONPATH` is stale). Not fixed by `claude login`. See `docs/TROUBLESHOOTING.md`.

## Layout

- `usage_guard/` — Python package (CLI + daemon)
- `skill/usage-guard/` — source skill copied by `install.sh` to `~/.claude/skills/`
- `tests/` — pytest, no network
- `scripts/check-public-clean.sh` — blocks Ring-2 / personal content before push (also CI)

## Public vs private

This git repo is **public**. Session handover, marketing drafts, and workspace notes live in the parent folder (outside this clone) and must never be committed here. Before pushing:

```bash
bash scripts/check-public-clean.sh
# or enable the hook once per clone:
git config core.hooksPath .githooks
```

## Conventions

- Minimal diffs; match existing style
- Control file fields: snake_case in `control.json`; camelCase in `get_usage()` return dict
- Weekly fields: `weekly_percent`, `weekly_resets_at`, `pause_reason`; config `weekly_enabled`, `weekly_threshold_pause`

## Verify before claiming done

- `pytest` passes
- For CLI changes: `python3 -m usage_guard doctor` or mock arm
- Read what you changed — trace skill ↔ control.json field names
