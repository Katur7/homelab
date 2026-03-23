# Milestone 03: Core Infrastructure Migration — Plan

**Date:** 2026-03-23
**Status:** In Progress

## Objective
Migrate the Traefik/CrowdSec/Redis/Authelia stack and Cloudflare Tunnel from OMV-managed
auto-generated compose files into the GitOps-controlled `infrastructure/` directory.

This milestone creates the `traefik_internal` and `traefik_tunnel` Docker networks that
all future service migrations depend on.

---

## Scope

### infrastructure/gateway/
Contains: Traefik reverse-proxy, socket-proxy, CrowdSec WAF, Redis session store, Authelia SSO.

### infrastructure/cloudflare/
Contains: cloudflared tunnel client, cloudflare-ddns DDNS updater.

---

## Pre-Migration Checklist
- [ ] `acme.json` copied to `infrastructure/gateway/config/acme.json` with `chmod 600`
- [ ] All secrets populated in `.env` files (git-ignored)
- [ ] `docker compose config` passes for both stacks
- [ ] Backup verified recent (Milestone 02 BorgBackup)

---

## Rollback Plan
If the new stack fails to start or services are unreachable:

1. Stop new stacks:
   ```bash
   docker compose -f /home/grimur/homelab/infrastructure/gateway/compose.yaml down
   docker compose -f /home/grimur/homelab/infrastructure/cloudflare/compose.yaml down
   ```
2. Re-enable OMV-managed stacks in OMV UI → Docker → Compose → Start
3. Verify `acme.json` at `/appdata/traefik/acme.json` is intact (never overwritten)
4. Named volume `crowdsec-db` is preserved — CrowdSec data not lost

**Key safety:** The original `/appdata/traefik/` and `/appdata/cloudflare/` files are
never deleted or modified. Rollback is always available.

---

## Impact Assessment
| Service | Impact during cutover | Recovery |
|---------|----------------------|----------|
| All Traefik-proxied services | Unreachable ~2 min | Auto-recover when new stack starts |
| Authelia (SSO) | Unavailable ~2 min | Session cookies survive restart |
| Cloudflare Tunnel | Disconnected ~1 min | Auto-reconnects |
| DDNS | Paused ~1 min | Resumes automatically |
| Let's Encrypt certs | No impact | `acme.json` preserved |
| CrowdSec banlists | No impact | Named volume `crowdsec-db` preserved |

---

## New File Locations
| Config | Old Path | New Path |
|--------|----------|----------|
| Traefik static config | `/appdata/traefik/traefik-config.yml` | `infrastructure/gateway/config/traefik.yml` |
| Traefik dynamic middlewares | `/appdata/traefik/dynamic/middlewares.yml` | `infrastructure/gateway/config/dynamic/middlewares.yml` |
| Traefik dynamic routes | `/appdata/traefik/dynamic/routes.yml` | `infrastructure/gateway/config/dynamic/routes.yml` |
| Authelia config | `/appdata/traefik/authelia/config/configuration.yml` | `infrastructure/gateway/config/authelia/configuration.yml` |
| CrowdSec config | `/appdata/traefik/crowdsec/config/` | `infrastructure/gateway/config/crowdsec/` |
| acme.json | `/appdata/traefik/acme.json` | `infrastructure/gateway/config/acme.json` (git-ignored) |
| DDNS config | `/appdata/cloudflare/ddns-config.json` | `infrastructure/cloudflare/config/ddns-config.json` |

---

## Cutover Steps
1. Stop cloudflare stack in OMV UI (or `docker compose -f /appdata/cloudflare/cloudflare.yml down`)
2. Stop traefik/gateway stack in OMV UI (or `docker compose -f /appdata/traefik/traefik.yml down`)
3. Start new stacks:
   ```bash
   cd /home/grimur/homelab
   docker compose -f infrastructure/gateway/compose.yaml up -d
   docker compose -f infrastructure/cloudflare/compose.yaml up -d
   ```
4. Verify: `docker ps` — all 7 containers should be running
5. Verify Traefik dashboard: https://traefik.internal.pippinn.me
6. Verify Authelia: https://auth.pippinn.me
7. Verify an external service via Cloudflare tunnel
8. Disable the OMV-managed stacks in OMV UI to prevent auto-restart

---

## Secrets Required in .env Files

### infrastructure/gateway/.env
```
CLOUDFLARE_TOKEN=<from /appdata/traefik/traefik.env>
REDIS_PASSWORD=<from /appdata/traefik/traefik.env>
AUTHELIA_JWT_SECRET=<from /appdata/traefik/traefik.env>
AUTHELIA_SESSION_SECRET=<from /appdata/traefik/traefik.env>
AUTHELIA_ENCRYPTION_KEY=<from /appdata/traefik/traefik.env>
CROWDSEC_BOUNCER_KEY=<from /appdata/traefik/dynamic/middlewares.yml>
```

### infrastructure/cloudflare/.env
```
TUNNEL_TOKEN=<from /appdata/cloudflare/cloudflare.yml>
CF_API_TOKEN=<same as CLOUDFLARE_TOKEN above>
```
