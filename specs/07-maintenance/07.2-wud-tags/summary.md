# Milestone 07.2 Summary: WUD Tag Label Fixes

**Date:** 2026-03-29
**Status:** `COMPLETE`

---

## What Was Changed

### compose.yaml label changes

| Container | File | Change |
|-----------|------|--------|
| `homeassistant` | `services/home-assistant/compose.yaml` | Added `wud.tag.include=^\d{4}\.\d+\.\d+$` — excludes dev/nightly builds |
| `matter-server` | `services/home-assistant/compose.yaml` | Pinned `:stable` → `6.2.2`; added `wud.tag.include=^\d+\.\d+\.\d+$` |
| `ord_dagsins` | `services/home-assistant/compose.yaml` | Added `wud.watch=false` — user's own image, no upstream |
| `immich_machine_learning` | `services/immich/compose.yaml` | Added `wud.watch=false` — always same version as `immich_server` |
| `immich_postgres` (database) | `services/immich/compose.yaml` | Added `wud.watch=false` — major Postgres upgrades require manual Immich migration |
| `immich_redis` (valkey) | `services/immich/compose.yaml` | Added `wud.watch=false` — digest-pinned, WUD cannot track |
| `calibre-web` | `services/calibre-web/compose.yaml` | Added `wud.tag.include=^\d+\.\d+\.\d+-ls\d+$` — excludes old date-format tags |
| `sonarr` | `services/starr/compose.yaml` | Added `wud.tag.include=^\d+\.\d+\.\d+\.\d+-ls\d+$` — fixes LSCR semver misparse causing downgrade |
| `qbittorrent` | `services/starr/compose.yaml` | Added `wud.tag.include=^\d+\.\d+\.\d+-r\d+-ls\d+$` — excludes Ubuntu-era tags |
| `syncthing` | `services/syncthing/compose.yaml` | Added `wud.tag.include=^v\d+\.\d+\.\d+-ls\d+$` — excludes builder/intermediate tags |
| `crowdsec` | `infrastructure/gateway/compose.yaml` | Added `wud.tag.include=^v\d+\.\d+\.\d+$` — excludes RC and slim variant tags |
| `redis` (gateway) | `infrastructure/gateway/compose.yaml` | Added `wud.tag.include=^[\d.]+-alpine$` — excludes non-alpine distro variants |

### WUD registry fixes

| File | Change |
|------|--------|
| `infrastructure/wud/vars.env` | Renamed `WUD_REGISTRY_LSCR_USERNAME` → `WUD_REGISTRY_LSCR_PRIVATE_USERNAME` to match the `_PRIVATE_TOKEN` instance name in `.env` |
| `infrastructure/wud/.env` | Added `WUD_REGISTRY_HUB_AUTH_LOGIN` + `WUD_REGISTRY_HUB_AUTH_PASSWORD` — Docker Hub credentials to avoid anonymous 429 rate limits |

---

## Why

WUD was generating 8+ false-positive update alerts due to:
- LSCR 4-part semver tags being miscompared (sonarr showing a downgrade)
- Dev/nightly builds appearing as HA updates
- Different distro variants appearing as updates (redis alpine→trixie, crowdsec rc-slim)
- Digest-pinned images producing unresolvable WUD entries
- User-owned image with no upstream (`ord_dagsins`)

---

## Outcome

All false positives eliminated. Remaining UPDATE entries in WUD are genuine:
`homeassistant 2026.3.4`, `calibre-web ls376`, `qbittorrent ls447`, `radarr ls296`,
`immich_server v2.6.3`, `mealie v3.14.0`, `cloudflare-ddns 2.1.0`,
`matter-server 8.1.0` (major bump — review before applying).

`sonarr` downgrade false positive will clear on the next scheduled rescan (01:00 cron).

Both LSCR and Docker Hub registries now registered and authenticated in WUD.

---

## No Architecture / global.env Changes Required

WUD configuration only. No new secrets exposed externally.

## Deviations from Plan

- Gateway `redis` (separate from immich's valkey) also needed a tag filter — added in the same pass.
- `crowdsec` RC filter added after user request — not in original plan scope.
- LSCR `vars.env` typo fixed opportunistically (`USERNAME` → `PRIVATE_USERNAME`).
- Docker Hub credentials added to WUD `.env` to resolve 429 rate limiting.
