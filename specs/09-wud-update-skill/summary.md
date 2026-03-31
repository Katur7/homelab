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

## WUD sonarr bug — root cause and fix (2026-03-31)

**Root cause:** GHCR returns tags in lexicographic (alphabetical) order. WUD picks the alphabetically-last matching tag as "latest". For 4-part linuxserver tags (`A.B.C.D-lsNNN`), this is wrong: `4.0.9.2244-ls257` sorts after `4.0.17.2952-ls305` because `9 > 1` character-by-character. WUD therefore reported `4.0.9.2244-ls257` as the newest available version — a false downgrade.

**Fix:** Added `wud.tag.transform=^(\\d+\\.\\d+\\.\\d+)\\.\\d+(-ls\\d+)$$ => $$1$$2` to radarr, sonarr, and prowlarr in `services/starr/compose.yaml`. This strips the 4th version component before comparison, giving WUD valid 3-part semver (`4.0.17-ls305` vs `4.0.9-ls257`) that it compares numerically. Sonarr now correctly shows `updateAvailable: false`.

**Applied proactively to:** radarr and prowlarr — both use the same 4-part format and will hit the same bug on their next double-digit patch release (e.g. radarr `6.0.9` → `6.0.10`).

**Latent risk — qbittorrent:** Uses 3-part `A.B.C-rN-lsNNN` format (valid semver), so WUD may compare correctly for now. However the same alphabetic ordering bug will occur if any version component reaches double digits (e.g. `5.1.9` → `5.1.10`). The same transform cannot be applied (no 4th component to strip). Fix at that point: strip `-r\d+-ls\d+` for comparison, accepting loss of ls-only update detection, or investigate a padding-based transform.

## Known issues / follow-up

- **`AskUserQuestion` confirmed working** for button-based update gate.
