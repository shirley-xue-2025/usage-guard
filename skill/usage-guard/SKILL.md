---
name: usage-guard
description: Arm proactive 5-hour usage protection for long Claude Code / Fable sessions. Invoke at session start only — external daemon monitors usage, session checks control file at safe checkpoints, pauses before extra wallet burn, resumes after reset.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit
argument-hint: [resume | your task description]
---

# usage-guard

Proactive usage guard for long Claude Code sessions (Desktop Code tab or CLI). **Invoke once at session start** before heavy Fable / batch work.

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

Read `~/.usage-guard/control.json` once and confirm `armed: true`.

---

## 2. Session contract (inform up front — before main work)

You are now **usage-guard armed**. Follow this for the rest of this session:

### Control file (only signal that matters)

- Path: `~/.usage-guard/control.json`
- Obey **`state` only**: `RUN` = continue, `PAUSE` or `COOLDOWN` = stop dispatching new work.
- **Never** decide pause/continue from `five_hour_percent` yourself.

### Checkpoint file

- Path: `~/.usage-guard/sessions/<session_id>/checkpoint.json` (session_id from control.json)
- After **every completed unit** (file, batch item, subagent return): update checkpoint (`done`, `next`, `note`).
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
3. Tell the user: paused near 5-hour limit; daemon will notify at reset.
4. **Do not** start new subagents, batches, or long tool chains this turn.
5. Run self-paced `/loop` with delay from `session_check_seconds` in control.json (cap single sleep at 59m; chain if longer until `state == RUN`).

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
/loop Read ~/.usage-guard/control.json. If PAUSE/COOLDOWN: checkpoint and stop new work. If RUN: continue task from checkpoint. Use session_check_seconds for next delay.
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
- After force-quit Desktop, use `/usage-guard resume` in a **new** session.
