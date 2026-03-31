# Spec 09: WUD Update Review Skill — Summary

## What was changed

1. **Created `.claude/commands/check-updates.md`** — a Claude Code slash command (`/check-updates`) that:
   - Queries WUD at `https://update.internal.pippinn.me/api/containers` for containers with pending updates
   - Resolves release notes URLs via OCI source labels and a static lookup table
   - Fetches and summarises release notes from GitHub API, HA blog, or Gitea HTML
   - Flags breaking changes prominently (major bumps + keyword scanning)
   - Handles linuxserver `ls`-only bumps as a one-line note (no full fetch)
   - Offers to apply each update via `AskUserQuestion` button UI
   - Updates `compose.yaml` (or `.env` for env-var-pinned images), pulls, recreates, and verifies health
   - Reminds to commit all compose.yaml changes grouped at the end

2. **`services/vikunja/compose.yaml`** — added `wud.watch=false` to `vikunja-db` (postgres major upgrades require manual `pg_upgrade`, not appropriate for automated skill)

3. **`services/it-tools/compose.yaml`** — added `wud.tag.include=^\d{4}\.\d{2}\.\d{2}-[a-f0-9]{7}$` so WUD tracks date-hash releases

## Why it was changed

Manual container update tracking was ad-hoc. The skill provides a repeatable, reviewable workflow: check → read release notes → decide → apply — all within the Claude Code session, with git history as the audit trail.

## First run results (2026-03-31)

| Container | Result |
|---|---|
| cloudflare-ddns | ✅ `2.0.8` → `2.1.0` — dependency/size refactor, drop-in replacement |
| homeassistant | ✅ `2026.3.2` → `2026.3.4` — bug fixes across integrations |
| qbittorrent | ✅ `ls446` → `ls447` — base image update |
| radarr | ✅ `ls295` → `ls296` — base image update |
| matter-server | ✅ `6.2.2` → `8.1.0` — Matter 1.4 + Python 3.12, two major versions |
| sonarr | ⚠️ Skipped — WUD reporting downgrade (`4.0.9 < 4.0.17`), WUD bug |

## New secrets / variables

None.

## Architecture / global.env updates required

None.

## Known issues / follow-up

- **sonarr WUD bug:** WUD consistently reports `4.0.17.2952-ls305 → 4.0.9.2244-ls257` (a downgrade). Needs investigation — likely a WUD semver parsing issue with the 4-part linuxserver tag format.
- **`AskUserQuestion` confirmed working** for button-based update gate.
