# Manual checklist (repo owner)

Things that cannot be done from git — do these on GitHub / in the community.

## GitHub repo settings (~10 min)

Open: https://github.com/shirley-xue-2025/usage-guard/settings

### Description (copy-paste)

```
Proactive 5h usage guard for Claude Code (macOS). Pause before extra wallet on long Fable 5 / subagent runs. /usage-guard skill + external daemon. Not affiliated with Anthropic.
```

### Topics (copy-paste one per line)

```
claude-code
claude
anthropic
macos
fable
fable-5
usage-limits
claude-desktop
automation
skill
agentic
```

### General

- [ ] **Releases** — publish [v0.1.0](https://github.com/shirley-xue-2025/usage-guard/releases/new?tag=v0.1.0) if not done (copy notes from `CHANGELOG.md`)
- [ ] **Discussions** — Settings → General → Features → enable **Discussions**
- [ ] **About → Website** — `https://github.com/shirley-xue-2025/usage-guard#install-macos`
- [ ] **Social preview** (optional) — Settings → upload a 1280×640 image (screenshot of `usage-guard status` + Desktop Code tab)

## Issue: optional demo GIF (~15 min)

1. Record short flow: `/usage-guard` → `usage-guard status` → (mock or real) notification
2. Save as `docs/demo.gif` or upload to GitHub user-images and link from README `## Demo`

## Community (~30–60 min, high impact)

Pick **one** to start — authentic story works best.

### A. Reddit

Subreddits: r/ClaudeAI, r/ClaudeCode (if active)

Title idea: *Built a proactive 5h usage guard after Fable 5 burned my extra wallet (queued messages couldn't stop it)*

Link: https://github.com/shirley-xue-2025/usage-guard

### B. Claude Discord / forums

Share in **#claude-code** or tips channel when someone asks about limits / Fable / long runs — not drive-by spam.

### C. GitHub issue comment (helpful, not promotional)

On [anthropics/claude-code#36320](https://github.com/anthropics/claude-code/issues/36320) (auto-resume feature request):

> Community workaround for proactive pause: [usage-guard](https://github.com/shirley-xue-2025/usage-guard) — external daemon + `/usage-guard` skill, macOS, pauses before 100% …

### D. Ask for cross-link

Open a polite issue or PR on [claude-auto-retry](https://github.com/cheapestinference/claude-auto-retry) asking to list usage-guard under "Proactive complement".

### E. Awesome list PR

Use snippet in [docs/awesome-list-snippet.md](awesome-list-snippet.md).

## Optional later

- [ ] Blog post (dev.to / Medium): your force-quit story
- [ ] Star/watch your own repo (fine) and share link with one friend who hits the same pain
- [ ] Tweet/X thread with screenshot of 100% UI + "what I built"

## Do not

- Spam unrelated threads
- Claim "never hit limit" or official Anthropic endorsement
- Rename repo to Fable-only branding (keep `usage-guard`)
