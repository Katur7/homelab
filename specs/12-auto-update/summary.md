# Milestone 12: Auto-Update — Summary

## What Changed

### New: `infrastructure/wud/updater.py`
Python stdlib HTTP listener (`http.server.BaseHTTPRequestHandler`). Receives WUD webhook POSTs and applies container updates autonomously.

Update flow per container:
1. Check `wud.autoupdate=true` Docker label via `docker inspect` — skip if absent
2. Parse semver major from `image_tag_value` and `update_kind_remote_value` — skip if major bump
3. Record current image digest
4. `docker pull {image}:{new_tag}`
5. Edit compose.yaml tag in-place
6. `docker compose -f {compose_path} up -d {service}`
7. Poll 30s for `running`/`healthy`
8. Success → `git commit "Auto-update {service}: {old} → {new}"`
9. Failure → revert compose.yaml + `docker compose up -d --no-pull` + POST to HA webhook

### Modified: `infrastructure/wud/compose.yaml`
- Added `autoupdater` service (Python listener, `user: 1000:992` — runs as grimur/docker)
- Added `wud_internal` bridge network shared between WUD and autoupdater
- Mounts `/home/grimur/homelab` at same host path (required for correct compose volume resolution)
- Mounts `/var/run/docker.sock` directly (write access needed for pull/recreate)
- `extra_hosts: host.docker.internal:host-gateway` for HA webhook POST

### Modified: `infrastructure/wud/vars.env`
Added WUD HTTP trigger config:
- `WUD_TRIGGER_HTTP_AUTOUPDATE_URL` — points to `http://autoupdater:8080`
- `WUD_TRIGGER_HTTP_AUTOUPDATE_THRESHOLD=minor` — belt-and-suspenders, won't fire on major bumps

### Modified: 9 service compose files
Added `wud.autoupdate=true` label to safe-list containers:
`mealie`, `radarr`, `sonarr`, `prowlarr`, `qbittorrent`, `plex`, `calibre-web`, `syncthing`, `audiobookshelf`, `tools`, `update`

## Why It Was Changed

Manual `/check-updates` workflow required human approval for every update. Low-risk containers (media apps, linuxserver images) generate frequent minor/patch updates that don't warrant review. Auto-updating these frees up time for updates that matter (Immich, HA, Authelia, infrastructure).

## Safe List Rationale

Included: apps where a bad update is recoverable without data loss or auth disruption.
Excluded: infrastructure (Traefik, Authelia, CrowdSec, Cloudflare), databases (Postgres, MySQL, Valkey), and apps with complex upgrade paths (Immich, Home Assistant, Vikunja).

## New Secrets/Variables

| Variable | File | Purpose |
|---|---|---|
| `HA_WEBHOOK_URL` | `infrastructure/wud/.env` (gitignored) | HA webhook for failure notifications |

Webhook automation created in HA UI (webhook ID is the secret — not in repo).
Notification template uses `trigger.json.service`, `trigger.json.reason`, `trigger.json.old_tag`, `trigger.json.new_tag`.

## Deviations from Plan

- **`wud.trigger.include` labels** — WUD fires all triggers for all containers by default; opt-in is not supported trigger-side. Safe list is enforced by the listener via `docker inspect` label check instead.
- **Repo mount path** — changed from `/repo` to `/home/grimur/homelab` (same as host). Required so `docker compose` client and daemon resolve relative volume paths identically.
- **`user: 1000:992`** — autoupdater runs as grimur/docker group to ensure git objects and file edits are owned by the correct user.
- **vikunja updated unexpectedly** — fired before label gate existed; v2.2.2→v2.3.0 minor bump was benign.

## Architecture / global.env Updates Needed

None. `wud_internal` is an internal bridge network not referenced in `ARCHITECTURE.md`.
