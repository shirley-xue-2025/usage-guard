# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

## [0.1.10] - 2026-06-16

### Changed

- Skill: remove internal "brain session" wording; clarify ScheduleWakeup often works for one-shot COOLDOWN waits (model may use it or CronCreate)

## [0.1.9] - 2026-06-16

### Fixed

- **Skill COOLDOWN wake-ups:** align with Claude Code platform — `ScheduleWakeup` only inside dynamic `/loop`; brain sessions use `/loop` guard tick or `CronCreate` one-shot (not direct ScheduleWakeup)
- Forbidden passive endings ("ping me when reset"); TROUBLESHOOTING for missed wake-ups

## [0.1.8] - 2026-06-16

### Added

- **One-time macOS notification** when telemetry goes blind (3 null polls): prompts `claude login` or `usage-guard doctor`

## [0.1.7] - 2026-06-16

### Fixed

- **Blind telemetry:** when usage API returns null percent for 3+ polls, set `telemetry_lost` in control.json (was stuck `RUN` forever)
- `doctor` warns and exits non-zero when API connects but percent is null (was misleading ✓)
- OAuth path tries `cu --json` fallback when percent is null

### Changed

- Skill: do not trust `RUN` when `telemetry_lost: true`
- `usage-guard status` shows telemetry alert

## [0.1.6] - 2026-06-13

### Added

- `usage-guard doctor` shows installed version and optional GitHub update notice (24h cache)
- README **Updating** section: `git pull && ./install.sh`

### Changed

- `__version__` synced to releases (was stuck at 0.1.0)
- README/SKILL tone: long sessions + high window % at start (not Fable-only)

## [0.1.5] - 2026-06-13

### Fixed

- **join + checkpoint seam:** `join.sh` sets `sitting_session_id`; `checkpoint.sh` writes there by default (was silently polluting primary session)

### Added

- `already_armed` JSON: `task_ignored` / `task_note` when task passed to arm on live daemon; `checkpoint_writes_target`
- Skill: ScheduleWakeup path for non-`/loop` COOLDOWN waits; session-end window delta report; join vs resume decision tree

### Changed

- `usage-guard status` shows primary vs sitting checkpoint target

## [0.1.4] - 2026-06-13

### Added

- Precomputed timing fields: `seconds_until_five_hour_reset`, `five_hour_reset_local`, `five_hour_reset_pending`, `sleep_until_local`, `daemon_next_poll_local`
- `awaiting_post_reset_poll` + `percent_note` when reset passed but percent not yet re-polled
- `checkpoint --quiet` / `-q` for one-line confirmation
- `already_armed` arm JSON includes `action`, `guidance`, and enriched timing fields

### Changed

- Skill: never compare UTC; `already_armed` branch; post-reset stale-high percent; prefer `checkpoint.sh --quiet`
- `usage-guard status` shows local reset time and minutes-until-reset

## [0.1.3] - 2026-06-12

### Added

- `last_reset_at` in control.json when the 5-hour window resets (reset signal sessions can read)
- `active_session_ids` tracks multi-session arcs; `arm --join` / `join.sh` registers a sitting without restarting daemon

### Changed

- Arm JSON includes `five_hour_resets_at` after first poll
- Skill: post-reset null percent semantics, self-scheduled wake-ups, multi-session guidance, `session_check_seconds` purpose
- `usage-guard status` shows `last_reset_at`, `sleep_until`, active sessions

## [0.1.2] - 2026-06-12

### Added

- `sleep_until` in control.json during PAUSE/COOLDOWN (aligned with `five_hour_resets_at`)
- Arm JSON reports `prior_armed`, `prior_daemon_alive`, and `warning` when re-arming after stale guard

### Changed

- `session_check_seconds` during cooldown matches time until reset (capped at 59m), not fixed 5m polling
- Skill documents account-level vs per-session usage blind spot and re-arm-every-sitting expectation

## [0.1.1] - 2026-06-12

### Added

- `usage-guard checkpoint` CLI and `scripts/checkpoint.sh` for atomic checkpoint updates (avoids Write-tool read-first friction)
- `arm` waits up to 45s for first usage poll by default (`--no-wait` to skip)

### Changed

- Control `phase` is `waiting_first_poll` until daemon writes first telemetry
- Skill documents warmup semantics, manual follow when user names usage-guard without `/usage-guard`, and checkpoint.sh usage

## [0.1.0] - 2026-06-12

### Added

- `usage-guard` CLI: `doctor`, `arm`, `disarm`, `status`, `poll`
- Background daemon with adaptive usage polling (OAuth API, zero session tokens)
- `/usage-guard` Claude Code skill (arm, resume, subagent checkpoint rules)
- macOS notifications at 85% warning and 90% pause
- Checkpoint files per session under `~/.usage-guard/sessions/`
- `install.sh` for skill + CLI wrapper
- Mock mode (`--mock-percent`) for development without OAuth
- MIT license

### Known limitations

- macOS only
- Cooperative pause (session must follow skill rules)
- Requires `claude login` once for usage reads on Desktop-only setups
- Uses unofficial OAuth usage endpoint (may change)

[0.1.10]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.10
[0.1.9]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.9
[0.1.8]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.8
[0.1.7]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.7
[0.1.6]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.6
[0.1.5]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.5
[0.1.4]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.4
[0.1.3]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.3
[0.1.2]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.2
[0.1.1]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.1
[0.1.0]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.0
