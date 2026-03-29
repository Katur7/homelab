# Milestone 06 Summary: Application Service Migrations

**Date:** 2026-03-26
**Status:** `COMPLETE`

---

## What Was Done

Migrated all application stacks from OMV-managed `/appdata/` into the GitOps-controlled
`services/` directory. Zero containers now run from `/appdata/`.

| Sub-milestone | Services | Status |
|---------------|----------|--------|
| 06.1 IT-Tools | `tools` | ✅ |
| 06.2 Mealie | `mealie` | ✅ |
| 06.3 Calibre-web | `calibre-web` | ✅ |
| 06.4 Plex | `plex` | ✅ |
| 06.5 StarArr | radarr, sonarr, prowlarr, qbittorrent | ✅ |
| 06.6 Syncthing | `syncthing` | ✅ |
| 06.7 Vikunja | `vikunja`, `vikunja-db` | ✅ |
| 06.8 Audiobookshelf | `audiobookshelf` | ✅ |
| 06.9 Home Assistant | homeassistant, matter-server, ord_dagsins | ✅ |
| 06.10 Immich | immich-server, immich-ml, redis, postgres | ✅ |
| 06.11 Hello World | `hello` | ✅ (discovered during final check) |

---

## Key Decisions & Findings

**Volume strategy:** All service state moved from `/appdata/` into `services/<service>/`
subdirectories. These are gitignored but covered by BorgBackup, which already sources
`/home/grimur/homelab/`.

**PUID change 1001→1000:** The OMV global.env used PUID=1001. Our confirmed correct value
is 1000 (user `grimur`). All copied state dirs required `chown -Rh 1000:100`. NAS shares
(movies, tv, kids, books, downloads, syncthing, code) were also fixed.

**host.docker.internal pattern:** For `network_mode: host` containers (HA, matter-server),
`traefik.docker.network` is meaningless. Use `loadbalancer.server.url=http://host.docker.internal:<port>`
instead. `host.docker.internal` resolves to `172.17.0.1` via `extra_hosts` in the gateway.

**Digest pinning limitation:** Docker Hub does not support pulling by local image digest.
Switched Vikunja and Immich to semver tags (`vikunja:2.2.2`, `immich:v2.6.1`).

**compose-level variable substitution:** `env_file` only injects vars into the container
environment — not into compose file variable substitution. Values used in `image:`,
`environment:`, or volume paths must be in `.env` or hardcoded.

**HA config selective tracking:** Most of `services/home-assistant/config/` is gitignored,
but `configuration.yaml`, `sensors/`, and `templates/` are selectively un-ignored as
user-authored files.

---

## New Secrets Created

| Service | Variable | Location |
|---------|----------|----------|
| Vikunja | `VIKUNJA_DATABASE_PASSWORD`, `VIKUNJA_SERVICE_JWTSECRET`, `POSTGRES_PASSWORD` | `services/vikunja/.env` |
| Audiobookshelf | `LISSEN_APP_SECRET` | `services/audiobookshelf/.env` |
| Immich | `DB_PASSWORD`, `IMMICH_APP_AUTH_BYPASS_SECRET`, `IMMICH_VERSION` | `services/immich/.env` |

---

## ARCHITECTURE.md Update

Updated `💾 Volume Management` section to document the new service state strategy
(gitignored subdirs in `services/<service>/`, covered by BorgBackup).
