---
name: usage-guard
description: Arm proactive 5-hour usage protection for long Claude Code sessions (batch, subagents, high window % at start). Daemon reads account-level 5-hour window usage (not per-session). User types /usage-guard at session start. Re-arm every sitting. If user mentions usage-guard by name, read this file and run arm.sh.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read, Write, Edit
argument-hint: [resume | your task description]
---

# usage-guard

Proactive usage guard for long Claude Code sessions (Desktop Code tab or CLI). **Invoke once at session start** before heavy batch, subagent, or overnight work — especially when the account window is already partly used.

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
- Report go/no-go using arm JSON: `five_hour_percent`, `five_hour_reset_local`, `seconds_until_five_hour_reset`, `state` — **not** raw UTC strings

**If arm JSON has `"already_armed": true`** (daemon from a prior sitting):

- **Proceed** — guard is active; do not `--force` restart unless user asks.
- **Same arc, new sitting** → `join.sh --task "label"` (not arm with a task — task is ignored on already_armed; JSON includes `task_ignored` if you tried).
- **After join** → `checkpoint.sh` writes to `sitting_session_id` automatically (stored in control.json). Do **not** use primary `session_id` unless you pass `--session-id` intentionally.
- **Continuing paused work** → `/usage-guard resume` (not join, not fresh arm).

**Decision tree:** already_armed + same sitting → proceed on `checkpoint_writes_target` | new sitting same arc → join.sh | paused task → resume | dead daemon → arm fresh

**Warmup:** right after arm, `phase` may be `waiting_first_poll` with null telemetry while the daemon fetches usage. `arm.sh` blocks up to ~45s for the first poll. If `phase` is still `waiting_first_poll` after arm returns, the daemon is warming up — **do not** start heavy subagent batches yet; re-read control.json in a few seconds. If `five_hour_percent` stays null and daemon is dead (`usage-guard status` → daemon not running), stop and run `usage-guard doctor`.

---

## 2. Session contract (inform up front — before main work)

You are now **usage-guard armed**. Follow this for the rest of this session:

### Control file (only signal that matters)

- Path: `~/.usage-guard/control.json`
- Obey **`state` only**: `RUN` = continue, `PAUSE` or `COOLDOWN` = stop dispatching new work.
- **Exception — `telemetry_lost: true`:** usage API returned no 5h percent for several polls. Guard is **blind** — do **not** start heavy or long work; tell user to run `claude login` or `usage-guard doctor` (they may get a macOS notification). `state` may still say `RUN`.
- **Never** decide pause/continue from `five_hour_percent` yourself.
- **Never compare timestamps yourself** (`five_hour_resets_at`, `sleep_until`, etc.). UTC trips up models. Use precomputed fields only:
  - `seconds_until_five_hour_reset` — positive = reset not yet; negative or `five_hour_reset_pending: false` = reset time passed
  - `five_hour_reset_local` — for user-facing reports (local timezone, not UTC)
  - If `state` is **`RUN`**, continue — **do not** call percent "stale" because a UTC clock comparison looked past. Wrong timezone math caused false "reset already passed" bugs.
- **Post-reset poll lag:** `five_hour_reset_pending: false` + non-null `five_hour_percent` (e.g. 88% with reset time an hour ago) means the **old window's percent** until the daemon re-polls — not a reason to pause. Check `awaiting_post_reset_poll` and `percent_note`; trust **`state`**. Expect correction at `daemon_next_poll_at` / `daemon_next_poll_local`.
- After a **window reset**, `five_hour_percent` may be `null` until the daemon's next poll. If `state` is `RUN`, trust `state` (check `last_reset_at` if present) — do not wait for the user to return.
- **`session_check_seconds`** — recommended delay for self-paced `/loop` guard ticks while armed. During `PAUSE`/`COOLDOWN`, prefer **`sleep_until`** instead. Daemon polling is separate (`daemon_next_poll_at`).

### Checkpoint file

- Path: `~/.usage-guard/sessions/<session_id>/checkpoint.json` (session_id from control.json)
- After **every completed unit** (file, batch item, subagent return): update checkpoint (`done`, `next`, `note`).
- **Prefer bash** (atomic, no Read-before-Write harness issue):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/checkpoint.sh" --quiet --json '{"done":["item-id"],"next":"next-item","note":""}'
```

Or flags: `checkpoint.sh --quiet --done item-id --next "next-item" --note "" --task "short label for status"`

Set **`task`** on the first checkpoint (via `/usage-guard <task>` at arm, or `checkpoint.sh --task`) so `usage-guard status` stays readable.

### Multi-session arcs (brain + code session)

PAUSE/RUN is **account-level** (one daemon). Checkpoints are **per `session_id`**.

- First sitting: `/usage-guard <task>` (arms daemon; sets primary `session_id` and `sitting_session_id`).
- Later sitting (daemon already running): `join.sh --task "this sitting's label"` — sets `sitting_session_id` in control.json; **all `checkpoint.sh` writes go there** until the next arm/join.
- To **share one checkpoint chain** across sittings (advanced): pass `--session-id <existing>` to checkpoint.sh explicitly.
- **join** = new sitting, new checkpoint file, same daemon. **resume** = continue a **paused** task from checkpoint (COOLDOWN/PAUSE arc), not "daemon already live."

`active_session_ids` lists all sittings; `sitting_session_id` is the active checkpoint write target.

- User can run `usage-guard status` in Terminal to see progress if Desktop UI is stuck.

### Safe checkpoints (critical for subagents / long runs)

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
3. Tell the user: paused near 5-hour limit; daemon may macOS-notify at reset. **Do not** treat that as a substitute for scheduling your own wake-up below.
4. **Do not** start new subagents, batches, or long tool chains this turn.
5. During `COOLDOWN`, use **`sleep_until`** / `seconds_until_five_hour_reset` for wait duration — do **not** poll every 5 minutes.

   **Before ending this turn**, you **must** schedule a wake-up. **Forbidden:** ending with "ping me when reset", "tell me when you're back", or "message me after the window resets".

   Pick **one** path (in order of preference):

   **A. `/loop` guard tick (preferred)** — works in brain and code sessions:
   ```text
   /loop Read ~/.usage-guard/control.json. If PAUSE/COOLDOWN: checkpoint if needed; sleep until sleep_until (cap 59m per iteration; chain). If RUN: continue from checkpoint next.
   ```
   Dynamic `/loop` (no interval) uses `ScheduleWakeup` internally — that is the **only** supported use of ScheduleWakeup.

   **B. One-shot session cron** — if you are **not** starting `/loop`, schedule a single fire at reset:
   - Natural language: `in N minutes, re-read ~/.usage-guard/control.json; if RUN continue checkpoint next; if still COOLDOWN schedule again`
   - Or `CronCreate` one-shot pinned to `five_hour_reset_local` (+ ~3 min margin)
   - Chain: if still `COOLDOWN` after fire, schedule the next check (cap 59m steps)

   **C. Do not** call `ScheduleWakeup` directly outside an active dynamic `/loop` — platform docs say it is for `/loop` self-pace only; brain sessions that skip `/loop` should use A or B.

6. If wake scheduling fails (cron disabled, provider lacks loop-dynamic), say so explicitly and give `five_hour_reset_local` — checkpoint is still safe for `/usage-guard resume`.

### On `state == RUN` with existing checkpoint

Continue from `next` in checkpoint; skip items in `done`.

### Subagent discipline (long batch runs)

- Prefer **smaller** subagent batches when armed (e.g. 3–5 items, not 50).
- Before each dispatch: read control.json; if not `RUN`, do not dispatch.
- Main chat orchestrates workload so subagents respect the timetable — **no mid-run chat reminders**.

### Session wrap — report window delta

At session end (or before a long pause), tell the user:

- **5h window now:** `five_hour_percent`, `five_hour_reset_local`, `state`
- **Delta this sitting** if you recorded percent at arm/join (e.g. "4% → 41% this session")
- This is the most useful user-facing summary — report it even without subagents

---

## 3. Start work

If the user provided a task in `/usage-guard <task>`, begin it under the contract above using self-paced `/loop`.

Example loop prompt:

```text
/loop Read ~/.usage-guard/control.json. If PAUSE/COOLDOWN: checkpoint and stop new work; sleep until sleep_until (or session_check_seconds). If RUN: continue task from checkpoint.
```

---

## 4. RESUME MODE — `/usage-guard resume`

1. Read `~/.usage-guard/control.json` — if `state` is not `RUN`, tell user to wait (show `five_hour_reset_local` / `sleep_until_local`, or `seconds_until_*`).
2. Read checkpoint for `sitting_session_id` (or `checkpoint_writes_target` / primary `session_id` if no join).
3. Continue from `next`; dedupe using `done`.
4. Re-arm only if `armed` is false: run `arm.sh` again.

---

## 5. Limits (be honest with user)

- Cannot force-stop a running subagent from outside; guard prevents **new** work after PAUSE.
- Progress safety depends on frequent checkpoint writes.
- After force-quit Desktop, use `/usage-guard resume` in a **new** session (re-arms daemon if needed).
- Daemon exit does **not** keep the guard active — always `/usage-guard` or `/usage-guard resume` at the start of a sitting.
