# Agent notes — usage-guard repo

For Shirley's full workspace (marketing, handover, setup gate), read the **parent** folder:

`/Users/chao.xue/shirley/Usage Guard/WORKSPACE.md`

---

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

## Conventions

- Minimal diffs; match existing style
- Control file fields: snake_case in `control.json`; camelCase in `get_usage()` return dict
- Do not commit private Ring 2 docs (marketing-pack, SESSION-HANDOVER) into this repo

## Verify before claiming done

- `pytest` passes
- For CLI changes: `python3 -m usage_guard doctor` or mock arm
- Read what you changed — trace skill ↔ control.json field names
