---
name: usage-guard
description: Arm proactive 5-hour usage protection for long Claude Code / Fable sessions. Daemon reads account-level 5-hour window usage (not per-session) — catches blind spots when chat shows 58% but shared window is 94%. User types /usage-guard at session start (may not appear in slash picker — type it anyway). Re-arm every sitting; arms do not survive Desktop quit or daemon exit. If user mentions usage-guard by name without the slash command, read this file and run arm.sh.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit
argument-hint: [resume | your task description]
---

# usage-guard

Proactive usage guard for long Claude Code sessions (Desktop Code tab or CLI). **Invoke once at session start** before heavy Fable / batch work.

### Why account-level monitoring matters

Each Claude session only sees its own usage. The **shared 5-hour window** is account-level — you can start at 58% in one session while another tab or earlier work already pushed the window to 94%. The daemon polls the OAuth usage API (same as Desktop Settings) so the guard sees the real window, not just this chat's view.

### Re-arm every sitting

**Arms do not survive** Desktop quit, crash, or daemon exit. At the start of **every** new sitting, run `/usage-guard` (or `/usage-guard resume` if continuing a paused task). If `arm.sh` prints `"warning"`, the previous guard was stale — proceed with the new arm.

## If the user mentions usage-guard without `/usage-guard`

When the user says "use usage-guard", "pay attention to usage limits", or names this skill but does not run the slash command:

1. **Follow this file** (you are reading it — treat that as the contract).
2. Run `arm.sh` via bash before heavy work (same as ARM MODE below).
3. Tell the user: `/usage-guard` is the normal entry point; with `disable-model-invocation` it may not show in the slash picker — **typing `/usage-guard` still works**.

Do **not** auto-arm on your own initiative without the user asking for usage protection.

## When the user invokes `/usage-guard`

### Mode detection

- If the argument is `resume` (or starts with `resume`): **RESUME MODE** (skip arm, go to section 4).
- Otherwise: **ARM MODE**.

---

## 1. ARM MODE — start guard

Run:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/arm.sh" {{ARGUMENTS}}
```

If arm fails, **stop** and tell the user to run `usage-guard doctor` in Terminal. Do not start heavy work without a successful arm.

Read `~/.usage-guard/control.json` once and confirm:

- `armed: true`
- `phase` is `normal` (or `five_hour_percent` is set) — **not** stuck on `waiting_first_poll` without a live daemon
- If arm JSON output includes `"warning"`, tell the user the prior guard was not active and this is a fresh arm
- Report go/no-go using arm JSON: `five_hour_percent`, `five_hour_resets_at`, `state` (no second read required)

**Warmup:** right after arm, `phase` may be `waiting_first_poll` with null telemetry while the daemon fetches usage. `arm.sh` blocks up to ~45s for the first poll. If `phase` is still `waiting_first_poll` after arm returns, the daemon is warming up — **do not** start heavy subagent batches yet; re-read control.json in a few seconds. If `five_hour_percent` stays null and daemon is dead (`usage-guard status` → daemon not running), stop and run `usage-guard doctor`.

---

## 2. Session contract (inform up front — before main work)

You are now **usage-guard armed**. Follow this for the rest of this session:

### Control file (only signal that matters)

- Path: `~/.usage-guard/control.json`
- Obey **`state` only**: `RUN` = continue, `PAUSE` or `COOLDOWN` = stop dispatching new work.
- **Never** decide pause/continue from `five_hour_percent` yourself.
- After a **window reset**, `five_hour_percent` may be `null` until the daemon's next poll. If `state` is `RUN`, trust `state` (check `last_reset_at` if present) — do not wait for the user to return.
- **`session_check_seconds`** — recommended delay for self-paced `/loop` guard ticks while armed. During `PAUSE`/`COOLDOWN`, prefer **`sleep_until`** instead. Daemon polling is separate (`daemon_next_poll_at`).

### Checkpoint file

- Path: `~/.usage-guard/sessions/<session_id>/checkpoint.json` (session_id from control.json)
- After **every completed unit** (file, batch item, subagent return): update checkpoint (`done`, `next`, `note`).
- **Prefer bash** (atomic, no Read-before-Write harness issue):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/checkpoint.sh" --json '{"done":["item-id"],"next":"next-item","note":""}'
```

Or flags: `checkpoint.sh --done item-id --next "next-item" --note "" --task "short label for status"`

Set **`task`** on the first checkpoint (via `/usage-guard <task>` at arm, or `checkpoint.sh --task`) so `usage-guard status` stays readable.

### Multi-session arcs (brain + code session)

PAUSE/RUN is **account-level** (one daemon). Checkpoints are **per `session_id`**.

- First sitting: `/usage-guard <task>` (arms daemon, sets primary `session_id`).
- Later sitting (daemon already running): `bash "${CLAUDE_SKILL_DIR}/scripts/join.sh" --task "code session label"` — adds a checkpoint without restarting the daemon or overwriting the primary id.
- To **share one checkpoint chain**, reuse the same id: `arm.sh` with `--session-id <existing>` (advanced).
- On resume, read checkpoint for **your** `sitting_session_id` if you joined; default `session_id` in control.json is the primary.

`active_session_ids` in control.json lists all sittings on this arc.

- User can run `usage-guard status` in Terminal to see progress if Desktop UI is stuck.

### Safe checkpoints (critical for Fable / subagents)

Read control.json only at these times:

1. Before starting the main task loop
2. **Before dispatching each subagent or parallel batch**
3. After each subagent returns
4. Before starting any new multi-step tool sequence expected to take >10 minutes
5. At each `/loop` iteration dedicated to guard checks

**Never** rely on the user sending a chat message mid-run — messages queue during subagent work.

### On `state == PAUSE` or `COOLDOWN`

1. Finish the **current atomic unit** only — do not abandon mid-write.
2. Update checkpoint with `done`, `next`, clear `note`.
3. Tell the user: paused near 5-hour limit; macOS may notify at reset (CLI sessions won't see it — poll `control.json`).
4. **Do not** start new subagents, batches, or long tool chains this turn.
5. During `COOLDOWN`, use **`sleep_until`** (or `session_check_seconds`, which is set to ~remaining time until reset) for `/loop` delay — do **not** poll every 5 minutes while waiting for reset. Cap single `/loop` sleep at 59m; chain if `sleep_until` is still in the future until `state == RUN`.
6. **Schedule your own wake-up** — poll `control.json` after `sleep_until` (or confirm via `last_reset_at`). **Never** end the turn with "tell me when you're back"; blocked on reset = self-scheduled poll.

### On `state == RUN` with existing checkpoint

Continue from `next` in checkpoint; skip items in `done`.

### Subagent discipline (Fable)

- Prefer **smaller** subagent batches when armed (e.g. 3–5 items, not 50).
- Before each dispatch: read control.json; if not `RUN`, do not dispatch.
- Main chat orchestrates workload so subagents respect the timetable — **no mid-run chat reminders**.

---

## 3. Start work

If the user provided a task in `/usage-guard <task>`, begin it under the contract above using self-paced `/loop`.

Example loop prompt:

```text
/loop Read ~/.usage-guard/control.json. If PAUSE/COOLDOWN: checkpoint and stop new work; sleep until sleep_until (or session_check_seconds). If RUN: continue task from checkpoint.
```

---

## 4. RESUME MODE — `/usage-guard resume`

1. Read `~/.usage-guard/control.json` — if `state` is not `RUN`, tell user to wait (show `resume_at` / `five_hour_resets_at`).
2. Read checkpoint for this `session_id`.
3. Continue from `next`; dedupe using `done`.
4. Re-arm only if `armed` is false: run `arm.sh` again.

---

## 5. Limits (be honest with user)

- Cannot force-stop a running subagent from outside; guard prevents **new** work after PAUSE.
- Progress safety depends on frequent checkpoint writes.
- After force-quit Desktop, use `/usage-guard resume` in a **new** session (re-arms daemon if needed).
- Daemon exit does **not** keep the guard active — always `/usage-guard` or `/usage-guard resume` at the start of a sitting.
