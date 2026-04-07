# Milestone 11: Monitoring — Summary

## What was changed

### 11.1 — Uptime Kuma slim image
- `pi/services/uptime-kuma/compose.yaml`: image changed from `louislam/uptime-kuma:2` to `louislam/uptime-kuma:2-slim`

### 11.2 — nebula-sync push monitor
- `pi/services/pihole/compose.yaml`: added `WEBHOOK_SYNC_SUCCESS_URL=${UPTIME_PUSH_URL}` to nebula-sync service
- `pi/services/pihole/.env` (not committed): added `UPTIME_PUSH_URL=http://192.168.86.26:3001/api/push/...`
- Direct IP used (not hostname) to avoid Docker DNS issues and Traefik access log noise
- Push monitor configured in Uptime Kuma UI: type=Push, name=nebula-sync, interval=10 min

### 11.3 — Uptime Kuma → HA notifications
- `services/home-assistant/config/configuration.yaml`: added `notify: !include notify.yaml` and `homeassistant: packages: !include_dir_named packages/`
- `services/home-assistant/config/notify.yaml` (not committed — contains device name): defines `notify.grimur_mobile_phones` group wrapping `mobile_app_pixel_7a`
- Uptime Kuma configured in UI: notification type=Home Assistant, URL=`http://192.168.86.17:8123` (direct IP), service=`grimur_mobile_phones`

### 11.4 — Beszel system monitoring
- `pi/services/beszel/compose.yaml`: Beszel Hub + Pi agent. Hub on port 8090, agent on port 45876 (`network_mode: host`). `APP_URL=https://monitoring.internal.pippinn.me`, `HUB_URL=http://localhost:8090`
- `services/beszel-agent/compose.yaml`: NAS agent. Port 45876 (`network_mode: host`). `HUB_URL=http://192.168.86.26:8090`
- `infrastructure/gateway/config/dynamic/routes.yml`: added `monitoring` router + service → `http://192.168.86.26:8090`
- `.gitignore`: added `pi/services/beszel/data/`, `pi/services/beszel/beszel_agent_data/`, `services/beszel-agent/beszel_agent_data/`
- Beszel → HA alert: webhook URL format `generic+http://192.168.86.17:8123/api/webhook/<id>?template=json`; HA automation reads `{{ trigger.json.message }}`

## Why it was changed
- Slim image reduces attack surface on Pi
- nebula-sync push monitor provides dead-man's switch for DNS sync — failure to sync triggers alert automatically
- HA notifications centralise alerting to mobile; `notify.grimur_mobile_phones` group decouples alerts from specific device
- Beszel provides CPU/memory/disk metrics for both hosts; Hub on Pi keeps monitoring independent of NAS availability

## Secrets / variables created

| Secret | Location | Purpose |
|--------|----------|---------|
| `UPTIME_PUSH_URL` | `pi/services/pihole/.env` | nebula-sync push monitor heartbeat URL |
| Uptime Kuma HA token | Uptime Kuma UI + HA profile | Uptime Kuma → HA API auth |
| `notify.yaml` device name | `services/home-assistant/config/notify.yaml` (not committed) | HA notify group definition |
| Beszel admin credentials | Beszel DB (`pi/services/beszel/data/`) | Hub web UI login |
| `BESZEL_AGENT_KEY_PI` | `pi/services/beszel/.env` | Hub → Pi agent auth |
| `BESZEL_AGENT_TOKEN_PI` | `pi/services/beszel/.env` | Pi agent → Hub registration |
| `BESZEL_AGENT_KEY_NAS` | `services/beszel-agent/.env` | Hub → NAS agent auth |
| `BESZEL_AGENT_TOKEN_NAS` | `services/beszel-agent/.env` | NAS agent → Hub registration |
| Beszel → HA webhook ID | Beszel UI + HA automations | Alert delivery |

## Notes
- `notify.yaml` is intentionally not committed (contains phone device name). Recreate manually: `platform: group`, name: `grimur_mobile_phones`, service: `mobile_app_pixel_7a`
- All internal webhook calls use direct IPs — avoids Docker DNS resolution issues with `*.internal.pippinn.me` hostnames and prevents Traefik access log noise
- Beszel webhook requires `?template=json` query param for Shoutrrr to send JSON body; without it HA receives an empty `MultiDictProxy`

## ARCHITECTURE.md update required
Yes — see below.
