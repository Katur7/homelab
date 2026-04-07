# Milestone 11: Monitoring

## Overview

Four sub-milestones to build out a complete monitoring and alerting stack:

| Sub | Title | Risk |
|-----|-------|------|
| 11.1 | Switch uptime-kuma to `-slim` image | Low |
| 11.2 | nebula-sync push monitor in Uptime Kuma | Low |
| 11.3 | Uptime Kuma → HA notifications | Low |
| 11.4 | Beszel system monitoring (Hub on Pi, Agent on NAS + Pi) | Medium |

---

## 11.1 — Uptime Kuma slim image

**File:** `pi/services/uptime-kuma/compose.yaml`

Change image from `louislam/uptime-kuma:2` to `louislam/uptime-kuma:2.X.X-slim` (pin to a specific version — check [Docker Hub](https://hub.docker.com/r/louislam/uptime-kuma/tags) for the latest `2.x.x-slim` tag before executing).

The `-slim` variant strips build tools and dev dependencies, reducing image size and attack surface. Data volume is unchanged; rollback is a tag revert + `docker compose up -d`.

**Rollback:** revert tag, `docker compose up -d`.

---

## 11.2 — nebula-sync push monitor

**How it works:** Uptime Kuma's "Push" monitor type waits for the monitored service to call a heartbeat URL. If no call arrives within the configured interval, Uptime Kuma marks it down — a natural dead-man's switch. nebula-sync supports `WEBHOOK_SYNC_SUCCESS_URL` which is called after each successful sync run.

### Uptime Kuma (manual)
1. Create a new monitor: **Type = Push**, Name = `nebula-sync`, interval = **10 minutes** (sync runs every 5 min — gives one missed cycle as buffer).
2. Copy the generated push URL (contains a secret token).

### Compose change
**File:** `pi/services/pihole/compose.yaml`

Add to `nebula-sync` environment:
```yaml
- WEBHOOK_SYNC_SUCCESS_URL=${UPTIME_PUSH_URL}
```

**File:** `pi/services/pihole/.env` (gitignored — never commit)
```
UPTIME_PUSH_URL=<push URL from Uptime Kuma>
```

### monitors.md
Update to document the push monitor and remove the "limitation" note about the DNS canary being unable to detect ongoing failures — the push monitor now handles that.

**Rollback:** remove env var, delete monitor in Uptime Kuma UI.

---

## 11.3 — Uptime Kuma → HA notifications

**How it works:** Uptime Kuma sends a POST to an HA webhook URL when a monitor changes state. HA receives it via a webhook automation trigger and fires a mobile notification.

### Uptime Kuma (manual, in Settings → Notifications)
- Type: **Webhook**
- URL: HA webhook URL (secret — do not document here, configure only in UI)
- Method: POST
- Apply to all monitors (or specific ones as preferred)

### HA (manual, in automations)
Create an automation with:
- Trigger: `webhook` (assign a secret webhook ID)
- Action: `notify.mobile_app_<device>` with message from `{{ trigger.json.msg }}` (or similar — check Uptime Kuma's webhook payload format)

Neither the webhook URL nor ID is committed to the repo — they live in Uptime Kuma's `kuma.db` and HA's internal config respectively.

**Rollback:** delete notification in Uptime Kuma settings.

---

## 11.4 — Beszel system monitoring

### Architecture

```
Pi (192.168.86.26)
  └── Beszel Hub  :8090  (web UI, DB)
  └── Beszel Agent :45876 (Pi system metrics)

NAS (192.168.86.17)
  └── Beszel Agent :45876 (NAS system metrics + Docker socket)

Traefik (NAS) → monitoring.internal.pippinn.me → Pi:8090
```

- Hub on Pi keeps monitoring independent of NAS — if NAS goes down, Hub still works.
- Hub connects **outbound** to agents; agents do not initiate to the Hub.
- Agent on NAS needs Docker socket (read-only) for container stats.

### New files

**`pi/services/beszel/compose.yaml`** — Hub + Pi agent

```yaml
name: beszel

services:
  beszel:
    image: ghcr.io/henrygd/beszel:X.X.X
    container_name: beszel
    restart: unless-stopped
    ports:
      - "8090:8090"
    volumes:
      - ./data:/beszel_data
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  beszel-agent:
    image: ghcr.io/henrygd/beszel-agent:X.X.X
    container_name: beszel-agent
    restart: unless-stopped
    network_mode: host          # required for accurate host metrics
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      LISTEN: 0.0.0.0:45876
      KEY: ${BESZEL_AGENT_KEY_PI}
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**`pi/services/beszel/.env`** (gitignored)
```
BESZEL_AGENT_KEY_PI=<key from Beszel Hub UI>
```

**`services/beszel-agent/compose.yaml`** — NAS agent

```yaml
name: beszel-agent

services:
  beszel-agent:
    image: ghcr.io/henrygd/beszel-agent:X.X.X
    container_name: beszel-agent
    restart: unless-stopped
    network_mode: host
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    environment:
      LISTEN: 0.0.0.0:45876
      KEY: ${BESZEL_AGENT_KEY_NAS}
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**`services/beszel-agent/.env`** (gitignored)
```
BESZEL_AGENT_KEY_NAS=<key from Beszel Hub UI>
```

### Traefik file provider

**File:** `infrastructure/gateway/config/dynamic/routes.yml`

Add router + service for Beszel Hub:
```yaml
    monitoring:
      entryPoints:
        - websecure
      rule: "Host(`monitoring.internal.pippinn.me`)"
      service: monitoring

  services:
    monitoring:
      loadBalancer:
        servers:
          - url: "http://192.168.86.26:8090"
        passHostHeader: true
```

### DNS
```bash
./scripts/add-dns.sh monitoring
```
This adds `monitoring.internal.pippinn.me → 192.168.86.17` (Traefik on NAS) to the NAS PiHole, which nebula-sync will propagate to the Pi PiHole.

### Setup sequence
1. Deploy Hub on Pi: `cd pi/services/beszel && docker compose up -d`
2. Open `http://192.168.86.26:8090` → complete first-run (set admin credentials)
3. Add Pi system in Hub UI → copy the agent key
4. Add `KEY` to `pi/services/beszel/.env`, redeploy Pi agent
5. Add NAS system in Hub UI → copy the agent key
6. Add `KEY` to `services/beszel-agent/.env`, deploy NAS agent
7. Verify both agents appear connected in Hub UI
8. Configure Beszel → HA alert: Settings → Notifications → Webhook → HA webhook URL (secret, do not document here)
9. Deploy Traefik route (add to `routes.yml`) + run DNS script
10. Verify `https://monitoring.internal.pippinn.me` loads Beszel UI

### Secrets created
| Secret | Location | Purpose |
|--------|----------|---------|
| Beszel admin password | Beszel DB only | Hub web UI login |
| `BESZEL_AGENT_KEY_PI` | `pi/services/beszel/.env` | Hub→Pi agent auth |
| `BESZEL_AGENT_KEY_NAS` | `services/beszel-agent/.env` | Hub→NAS agent auth |
| Beszel→HA webhook URL | Beszel UI only | Alert delivery |

### Risks / red-team
- **Docker socket on agents:** grants read access to Docker daemon. Beszel agent only reads, but the socket is high-value. Acceptable for an internal-only host agent; mount as `:ro`.
- **Hub on Pi:** if Pi goes down, Beszel UI and alerting are unavailable. The trade-off is intentional — keeps monitoring independent of NAS. Uptime Kuma on Pi provides the primary uptime alerting anyway.
- **Agent key rotation:** if an agent key is compromised, regenerate in Hub UI and update `.env`. No other services are affected.
- **Port 45876 on NAS:** exposed on LAN only (`network_mode: host`). Not exposed via Traefik. Acceptable.
- **Version pinning:** pin Hub and Agent to the same version tag — they must match. Check `ghcr.io/henrygd/beszel` for the latest release before deploying.

### Rollback
- Remove entries from `routes.yml` and DNS record
- `docker compose down` on Hub (Pi) and Agent (NAS)
- Delete `pi/services/beszel/` and `services/beszel-agent/` directories

---

## ARCHITECTURE.md updates required
After completion:
- Add Beszel Hub to Pi host table (port 8090)
- Add `monitoring.internal.pippinn.me` to internal service list
- Note Beszel agent on NAS (port 45876, LAN-only)
