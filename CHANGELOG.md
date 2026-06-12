# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

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

[0.1.3]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.3
[0.1.2]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.2
[0.1.1]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.1
[0.1.0]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.0
