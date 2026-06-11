# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

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

[0.1.0]: https://github.com/shirley-xue-2025/usage-guard/releases/tag/v0.1.0
