# Milestone 13: External Exposure — Mealie & Home Assistant

## Goal

Expose Mealie publicly with full Authelia protection, and expose Home Assistant externally with the minimum surface required for mobile notification actions (webhook endpoint only).

---

## 13.A — Mealie

### Current state
- Router: `mealie.internal.pippinn.me` on `websecure` only
- No Authelia, no tunnel

### Target state
- Single domain `mealie.pippinn.me` on both `websecure` (LAN) and `tunnel` (external + Authelia)
- Pattern: identical to Vikunja (`todo.pippinn.me`)
- Authelia `two_factor` policy applies via existing wildcard rule — no Authelia config changes needed

### Changes

**`services/mealie/compose.yaml`** — replace single router with two:

```yaml
labels:
  - "wud.autoupdate=true"
  - "traefik.enable=true"
  - "traefik.docker.network=traefik_internal"

  # Internal (LAN only — global internal-only middleware applies)
  - "traefik.http.routers.mealie-internal.entrypoints=websecure"
  - "traefik.http.routers.mealie-internal.rule=Host(`mealie.pippinn.me`)"

  # Tunnel (external — Authelia two_factor)
  - "traefik.http.routers.mealie-tunnel.entrypoints=tunnel"
  - "traefik.http.routers.mealie-tunnel.rule=Host(`mealie.pippinn.me`)"
  - "traefik.http.routers.mealie-tunnel.middlewares=authelia-auth@file"
```

**PiHole DNS** — add `mealie.pippinn.me`:
```bash
./scripts/add-dns.sh mealie
```

**Cloudflare Tunnel** — add public hostname:
- Subdomain: `mealie`
- Domain: `pippinn.me`
- Service: `https://traefik:8443` (same as all other public services)

### Rollback
Revert compose to single `websecure` router with `mealie.internal.pippinn.me`. Remove Cloudflare hostname. Remove PiHole DNS record.

---

## 13.B — Home Assistant

### Current state
- Router: `home-assistant.pippinn.me` on `websecure,tunnel` (full path, no Authelia, no path restriction)
- The tunnel exposure was accidental — no Cloudflare route existed so it was inert

### Target state
- Two routers, split by entrypoint:
  - `websecure`: full path, LAN only (global `internal-only` middleware applies)
  - `tunnel`: restricted to `PathPrefix('/api/webhook/')` only — no Authelia
- No Authelia anywhere on HA (HA's own token/webhook auth is the gate)
- Companion app notification actions work externally via the device webhook (`/api/webhook/<device_id>`)
- HA dashboard, config UI, and full API are **not** reachable externally — VPN required

### Why webhook-only

The HA companion app sends notification action events by POSTing to `/api/webhook/<device_webhook_id>`. HA's `mobile_app` integration translates this into a `mobile_app_notification_action` event internally. Existing automation YAML (`medication_reminder.yaml`, `maintenance_reminder.yaml`) requires no changes.

Trade-off accepted: companion app cannot sync or refresh tokens when away from home — it will appear offline externally. Only notification action taps work.

### Changes

**`services/home-assistant/compose.yaml`** — split the single router into two:

```yaml
labels:
  - "traefik.enable=true"
  - "traefik.http.services.home-assistant.loadbalancer.server.url=http://host.docker.internal:8123"
  - "wud.tag.include=^\\d{4}\\.\\d+\\.\\d+$$"

  # Internal (LAN only — global internal-only middleware applies)
  - "traefik.http.routers.home-assistant-internal.entrypoints=websecure"
  - "traefik.http.routers.home-assistant-internal.rule=Host(`home-assistant.pippinn.me`)"

  # Tunnel (external — webhook path only, no Authelia)
  - "traefik.http.routers.home-assistant-tunnel.entrypoints=tunnel"
  - "traefik.http.routers.home-assistant-tunnel.rule=Host(`home-assistant.pippinn.me`) && PathPrefix(`/api/webhook/`)"
```

**Cloudflare Tunnel** — add public hostname:
- Subdomain: `home-assistant`
- Domain: `pippinn.me`
- Service: `https://traefik:8443`

**No changes to:**
- Authelia `configuration.yml` (Authelia is never in the chain for HA)
- HA automation YAML files
- Matter server or `ord_dagsins` containers

### Rollback
Revert compose to single combined router (`entrypoints=websecure,tunnel`, no path rule). Remove Cloudflare hostname.

---

## Execution Order

1. **13.A** — Mealie (lower risk, simpler)
   1. Update `compose.yaml` labels
   2. Add PiHole DNS (`add-dns.sh mealie`)
   3. `docker compose up -d` — verify `mealie.pippinn.me` reachable on LAN with Authelia prompt
   4. Add Cloudflare hostname
   5. Verify external access + Authelia two_factor flow

2. **13.B** — Home Assistant (higher risk due to live service)
   1. Verify or add PiHole DNS for `home-assistant.pippinn.me`
   2. Update `compose.yaml` labels
   3. `docker compose up -d` — verify LAN access unchanged (`websecure` router)
   4. Add Cloudflare hostname
   5. Verify: tap a notification action from outside LAN → automation fires in HA
   6. Verify: `home-assistant.pippinn.me/` returns 404 or connection refused externally (UI not exposed)

---

## Security Notes

- Mealie: protected by Authelia two_factor — same posture as Vikunja and Immich
- HA webhooks are designed as unauthenticated endpoints; security comes from the unguessable webhook ID embedded in the device registration. CrowdSec + rate limiting (from `external-no-auth-chain`) provides additional protection against scanning.
- HA UI, `/api/` (states, events, config), and `/auth/token` are NOT reachable externally.

## New Secrets / Variables

None. No new `.env` entries, no new Authelia OIDC clients, no new `global.env` entries.

## Architecture / global.env Updates Required

None.
