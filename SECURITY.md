# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Email **xc.shirley+github@gmail.com** with:

- Description of the issue
- Steps to reproduce
- Impact (e.g. credential exposure, arbitrary command execution)

We aim to respond within 7 days.

## What this tool touches

- Reads Claude OAuth credentials from **macOS Keychain** or `~/.claude/` (local only)
- Calls Anthropic's OAuth usage endpoint over HTTPS
- Writes state under `~/.usage-guard/` (local only)
- Installs a skill to `~/.claude/skills/usage-guard/`

It does not upload credentials or usage data to third-party servers.
