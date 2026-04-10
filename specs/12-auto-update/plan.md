# Milestone 12: Auto-Update

## Goal
WUD automatically applies updates to a safe list of containers without human approval. Unsafe or major-version updates are still handled manually via `/check-updates`.

## Decisions

### Listener
- New Python container defined in `infrastructure/wud/compose.yaml` alongside WUD
- `updater.py` lives at `infrastructure/wud/updater.py`
- Python stdlib only (`http.server.BaseHTTPRequestHandler`) — no pip dependencies, no Flask
- Receives WUD webhook POSTs, applies updates, commits on success

### Network
- New dedicated Docker network `wud_internal`
- Shared between WUD and the listener only — no Traefik exposure
- Not `internal: true` so listener can reach HA on host network

### Safe List
Managed via Docker label `wud.trigger.include=http.autoupdate` on each opted-in container. WUD filters natively — listener needs no safe-list logic.

Safe-list containers:
- `mealie`, `radarr`, `sonarr`, `prowlarr`, `qbittorrent`
- `plex`, `calibre-web`, `syncthing`, `audiobookshelf`, `it-tools`, `wud`

### Tag Strategy
Keep specific version pins in compose.yaml. Listener edits the tag in compose.yaml on a successful update.

### Major Version Gate
Listener parses semver from `image_tag_value` (current) and `update_kind_remote_value` (new). If `major(new) > major(current)`, skip the update — no notification, no action. Update remains visible in WUD UI for manual handling.

WUD trigger also set to `THRESHOLD=minor` as belt-and-suspenders.

**Parsing rule:** strip leading `v`, split on `.`, take first element as major.

| Image | Current tag | New tag | Major current | Major new | Decision |
|---|---|---|---|---|---|
| mealie | `v3.14.0` | `v3.15.0` | 3 | 3 | ✅ allow |
| mealie | `v3.14.0` | `v3.14.1` | 3 | 3 | ✅ allow |
| mealie | `v3.14.0` | `v4.0.0` | 3 | 4 | 🚫 block |
| radarr (post-transform) | `6.0.4-ls296` | `6.0.5-ls299` | 6 | 6 | ✅ allow |
| radarr (post-transform) | `6.0.4-ls296` | `6.0.4-ls299` | 6 | 6 | ✅ allow (ls-only bump) |
| radarr (post-transform) | `6.0.4-ls296` | `7.0.0-ls300` | 6 | 7 | 🚫 block |
| qbittorrent | `5.1.4-r2-ls447` | `5.1.5-r1-ls450` | 5 | 5 | ✅ allow |
| qbittorrent | `5.1.4-r2-ls447` | `5.1.4-r3-ls448` | 5 | 5 | ✅ allow (r-only bump) |
| qbittorrent | `5.1.4-r2-ls447` | `6.0.0-r1-ls451` | 5 | 6 | 🚫 block |

**Known limitation — date-based tags (it-tools):** `it-tools` uses `2024.10.22-7ca5933` format. The parsed "major" is the year (`2024`). A year rollover (`2025.x.x`) would be incorrectly blocked. Mitigation: WUD's `THRESHOLD=minor` belt-and-suspenders won't help here either. Accept the limitation — it-tools updates infrequently and a year rollover can be handled manually via `/check-updates`.

### Update Flow
1. WUD detects update, POSTs to listener webhook
2. Major version check — abort if major bump
3. Record old image digest (`docker inspect`)
4. Pull new image by explicit tag
5. Edit compose.yaml tag to new version
6. `docker compose up -d {service}`
7. Poll for 30s: pass if container status is `running` (or `healthy` if HEALTHCHECK defined)
8. On success: `git commit` — `Auto-update {service}: {old} → {new}`
9. On failure: revert compose.yaml, `docker compose up -d --no-pull {service}`, POST to HA webhook

### Docker Socket
Direct `/var/run/docker.sock` mount into listener container. Acceptable — container is on isolated network with no external exposure.

### Git
- Listener has repo mounted and git configured (name + email only, no push credentials)
- Commit on success, no push — auto-update commits ride along with next manual push

### Notifications
- Failure only — POST to HA webhook (`http://host.docker.internal:8123/api/webhook/{id}`)
- New HA webhook to be created for this purpose
- Webhook URL stored in `.env` (gitignored)
- `extra_hosts: host.docker.internal:host-gateway` in listener compose

### WUD Changes
- Add `WUD_TRIGGER_HTTP_AUTOUPDATE_*` config to `infrastructure/wud/vars.env`
- Listener service added to `infrastructure/wud/compose.yaml`

## Sub-milestones

### 12.1 — Listener + WUD wiring
- Add `wud_internal` network to WUD compose
- Add webhook trigger vars to `infrastructure/wud/vars.env`
- Add listener service to `infrastructure/wud/compose.yaml`
- Write `infrastructure/wud/updater.py`

### 12.2 — Safe-list labels
- Add `wud.trigger.include=http.autoupdate` to 11 compose files
- No container restarts required

### 12.3 — HA webhook automation
- Add HA webhook URL to `infrastructure/wud/.env`
- User creates webhook in HA and wires up notification automation

## Testing

### Before going live (prior to 12.2 labels)
1. `docker compose build autoupdater` — image builds, `docker-cli-compose` installs cleanly
2. `docker compose up -d` — both services start, `wud_internal` network created
3. `docker logs autoupdater` — confirms "Starting auto-updater on port 8080"
4. From inside WUD container: `docker exec update curl -X POST http://autoupdater:8080` — confirms WUD can reach autoupdater over `wud_internal`

### Dry-run with real payload
5. Craft payload from WUD UI (container with pending update), POST manually — confirm major version gate logic fires correctly
6. Check `docker logs autoupdater` after WUD fires first real trigger — verify `result.tag` and `image.tag.value` parse as expected

### After 12.2 labels applied
7. Trigger a real update — verify compose.yaml is edited, container restarts, commit appears in `git log`
8. Simulate failure (stop container mid-health-check) — verify rollback fires and HA notification arrives (after 12.3)

## Files Changed
| File | Change |
|---|---|
| `infrastructure/wud/compose.yaml` | Add listener service and `wud_internal` network |
| `infrastructure/wud/vars.env` | Add webhook trigger config |
| `infrastructure/wud/updater.py` | New — Python stdlib HTTP listener |
| `infrastructure/wud/.env` | Add HA webhook URL (12.3) |
| `services/{safe-list}/compose.yaml` × 11 | Add `wud.trigger.include=http.autoupdate` label (12.2) |

## Impact on Other Services
- WUD: gains a new trigger and co-located listener service — no behaviour change for existing triggers
- Safe-list containers: label addition only, no restart required
- HA: new webhook automation to wire up

## Rollback
- Remove `WUD_TRIGGER_WEBHOOK_AUTOUPDATE_*` vars and listener service from WUD compose — trigger stops firing
- Remove `wud.trigger.autoupdate=true` labels (or leave — harmless with trigger gone)
- Any commits made by the listener are real commits; revert manually if needed
