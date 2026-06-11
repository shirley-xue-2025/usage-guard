# Security policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes       |

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Use **[GitHub Private vulnerability reporting](https://github.com/shirley-xue-2025/usage-guard/security/advisories/new)** (Security → Advisories → Report a vulnerability).

If that is unavailable, open a **private** [GitHub Discussion](https://github.com/shirley-xue-2025/usage-guard/discussions) or contact the maintainer via their GitHub profile.

Include:

- Description of the issue
- Steps to reproduce
- Impact (e.g. credential exposure, arbitrary command execution)

## What this tool touches

- Reads Claude OAuth credentials from **macOS Keychain** or `~/.claude/` (local only)
- Calls Anthropic's OAuth usage endpoint over HTTPS
- Writes state under `~/.usage-guard/` (local only)
- Installs a skill to `~/.claude/skills/usage-guard/`

It does not upload credentials or usage data to third-party servers.
