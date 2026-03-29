# Milestone 07.2 Plan: WUD — Fix Tag Label False Positives

**Date:** 2026-03-29
**Status:** `PLANNED`

---

## Problem

WUD is reporting 7 false positives and has 2 pin-quality violations.
Identified via WUD API audit on 2026-03-29.

---

## Confirmed False Positives

| Container | Current → "Update" | Root cause | Fix |
|-----------|-------------------|------------|-----|
| `calibre-web` | `0.6.26-ls375` → `2021.12.16` | Picks up old date-format tags | `wud.tag.include=^\d+\.\d+\.\d+-ls\d+$` |
| `homeassistant` | `2026.3.2` → `2026.5.0.dev...` | Dev/nightly builds not excluded | `wud.tag.include=^\d{4}\.\d+\.\d+$` |
| `immich_machine_learning` | v2.6.1 → v2.6.3 | Always same version as immich_server — redundant watch | `wud.watch=false` |
| `immich_postgres` | `14-vectorchord...` → `18-vectorchord...` | Major Postgres upgrade requires manual Immich-guided migration | `wud.watch=false` |
| `qbittorrent` | `5.1.4-r2-ls446` → `20.04.1` | Picks up Ubuntu-era tags via incorrect semver parse | `wud.tag.include=^\d+\.\d+\.\d+-r\d+-ls\d+$` |
| `redis` (valkey) | `8-bookworm@sha256:...` — digest-pinned | WUD cannot track digest pins; shows stale data | `wud.watch=false` (**not** a tag filter — actual image is `valkey/valkey:8-bookworm`, not `redis:8.6-alpine`) |
| `sonarr` | `4.0.17.2952-ls305` → `4.0.9.2244-ls257` | **Downgrade** — WUD misparses LSCR build number as semver | `wud.tag.include=^\d+\.\d+\.\d+\.\d+-ls\d+$` |
| `syncthing` | `v2.0.15-ls211` → `version-v2.0.15` | Picks up builder/intermediate tag | `wud.tag.include=^v\d+\.\d+\.\d+-ls\d+$` |

**Out of scope (already have correct labels):** `radarr` and `prowlarr` in `services/starr/compose.yaml`
already have `wud.tag.include=^\d+\.\d+\.\d+\.\d+-ls\d+$` — confirmed by reading the file.

---

## Pin Quality Fixes (same pass)

| Container | Issue | Fix |
|-----------|-------|-----|
| `ord_dagsins` | Uses `:latest` (user's own image — no upstream to track) | `wud.watch=false` |
| `matter-server` | Uses `:stable` channel tag — untrackable | Pin image to `6.2.2` (latest stable as of 2026-03-29) + `wud.tag.include=^\d+\.\d+\.\d+$` |
| `mealie` | No label needed — default semver watch is correct, want to know when v4 ships | No change |

**Also noted (not actioned here):** `socket-proxy: 1` and `traefik-proxy: v3.6` use
major/minor-only pins — review in a future update pass.

---

## Docker Label Escaping Convention

In Docker Compose label strings, regex special characters must be double-escaped and `$` anchors
use `$$` to prevent compose variable interpolation. Examples from existing labels in the repo:

```
"wud.tag.include=^\\d+\\.\\d+\\.\\d+\\.\\d+-ls\\d+$$"
```

(`\d` → `\\d`, `\.` → `\\.`, `$` → `$$`)

---

## Additional: Docker Hub Rate Limiting (429 errors)

WUD logs show HTTP 429 errors from Docker Hub during the 01:00 cron run. This is caused by
anonymous pull rate limits. Fix: add Docker Hub credentials to WUD's `.env`
(`infrastructure/wud/.env`):

```
WUD_REGISTRY_HUB_LOGIN=<dockerhub_username>
WUD_REGISTRY_HUB_PASSWORD=<dockerhub_pat>
```

PAT scope required: **Read public repositories** only. Create at hub.docker.com → Account Settings
→ Personal Access Tokens.

After adding, restart WUD: `docker compose up -d` in `infrastructure/wud/`.
No other container restarts needed.

---

## Files to Change

| File | Change |
|------|--------|
| `services/home-assistant/compose.yaml` | Add `wud.tag.include` to `homeassistant`; pin `matter-server` to `6.2.2` + add label; `wud.watch=false` on `ord_dagsins` |
| `services/mealie/compose.yaml` | No change — default WUD watch is sufficient |
| `services/immich/compose.yaml` | `wud.watch=false` on `immich_machine_learning`, `immich_postgres` (database), and `redis` (valkey) |
| `services/calibre-web/compose.yaml` | Add `wud.tag.include=^\d+\.\d+\.\d+-ls\d+$` |
| `services/starr/compose.yaml` | Add `wud.tag.include` to `sonarr` and `qbittorrent` only (radarr + prowlarr already done) |
| `services/syncthing/compose.yaml` | Add `wud.tag.include=^v\d+\.\d+\.\d+-ls\d+$` |
| `infrastructure/gateway/compose.yaml` | Add `wud.tag.include=^v\d+\.\d+\.\d+$` to `crowdsec` (exclude RC tags); add `wud.tag.include=^[\d.]+-alpine$` to gateway `redis` (exclude non-alpine variants) |
| `infrastructure/wud/.env` | Add `WUD_REGISTRY_HUB_LOGIN` + `WUD_REGISTRY_HUB_PASSWORD` (user must supply credentials) |

---

## Rollback

Remove the added WUD labels from affected `compose.yaml` files and run
`docker compose up -d` in each stack. WUD will revert to its default broad-match behaviour.
