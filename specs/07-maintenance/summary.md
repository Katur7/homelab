# Milestone 07 Summary: Infrastructure Maintenance & Tuneup

**Date:** 2026-03-29 → 2026-03-30
**Status:** `COMPLETE`

---

## What Was Done

| # | Sub-milestone | Outcome |
|---|---------------|---------|
| 07.1 | Traefik access log → JSON | `format: common` → `format: json` in `traefik.yml`. CrowdSec parser confirmed to support both formats — no acquis change needed. |
| 07.2 | WUD tag label false positives | 7 false positives eliminated. Labels added to `calibre-web`, `homeassistant`, `sonarr`, `qbittorrent`, `syncthing`. `wud.watch=false` on `immich_machine_learning`, `immich_postgres`, `immich_redis`, `ord_dagsins`. `matter-server` pinned to `6.2.2`. Docker Hub credentials added to WUD `.env` (fixes 429 rate limit errors). LSCR `vars.env` corrected (`WUD_REGISTRY_LSCR_PRIVATE_USERNAME`). |
| 07.3 | Tailscale activated | Image pinned to `v1.94.2`. Stale `TS_AUTHKEY` removed from `.env`. Container started — node came online immediately using existing `tailscaled.state` (no new auth key needed). Tailscale IP: `100.107.106.77`. |
| 07.4 | OMV email noise | Fail2Ban: custom `sendmail-whois-lines-banonly` action created — suppresses start/stop emails, keeps ban alerts (SSH only). OMV UI: web login notifications disabled (Authentication events). BorgBackup cron email output disabled for old `/appdata` job. |
| 07.5 | WireGuard MTU | `MTU = 1320` added to all 7 config files (server, 4 peers, 2 templates). 1320 was already validated on GrimurFlandri; the mismatch with the server default of 1420 was the cause of slow speeds. Applied live via `ip link set`. |
| 07.6 | Home Assistant log audit | No config errors found. Identified: BADRING sensor Zigbee delivery failures (hardware check needed), Aqara master bedroom dimmer intermittent signal loss (monitor), bootstrap slow-load warnings are expected behaviour (not failures). |

---

## Files Changed

| File | Change |
|------|--------|
| `infrastructure/gateway/config/traefik.yml` | `accesslog.format: json` |
| `infrastructure/wud/vars.env` | LSCR registry username corrected |
| `services/home-assistant/compose.yaml` | HA dev-build tag filter; `matter-server` pinned to `6.2.2`; `ord_dagsins` `wud.watch=false` |
| `services/immich/compose.yaml` | `wud.watch=false` on `immich_machine_learning`, `immich_postgres`, `immich_redis` |
| `services/calibre-web/compose.yaml` | LSCR tag filter |
| `services/starr/compose.yaml` | LSCR tag filters for `sonarr` and `qbittorrent` |
| `services/syncthing/compose.yaml` | LSCR tag filter |
| `infrastructure/tailscale/compose.yaml` | Image pinned to `v1.94.2` |
| `infrastructure/wireguard/config/*` | `MTU = 1320` on all 7 files (gitignored — private keys) |

**Outside repo (system-managed):**
- `/etc/fail2ban/jail.local` — ban-only action override
- `/etc/fail2ban/action.d/sendmail-whois-lines-banonly.conf` — custom action

---

## Secrets / Variables Created

| Variable | Where | Purpose |
|----------|-------|---------|
| Docker Hub credentials | `infrastructure/wud/.env` (gitignored) | Fix WUD 429 rate limit errors on Docker Hub pulls |

---

## Follow-up Items (not blocking)

- **BADRING Water Leakage Sensor** — check battery and Zigbee range
- **Aqara master bedroom dimmer** — monitor for recurring Zigbee signal loss; add router device nearby if it persists
- **WireGuard peer configs** — distribute updated `.conf` files (or new QR codes) to `GrimurPixel` and `Tryggvi` so client-side MTU takes effect

## No Architecture / global.env Changes Required
