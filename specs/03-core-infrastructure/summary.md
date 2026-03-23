# Milestone 03 Summary: Core Infrastructure Migration

**Date:** 2026-03-23
**Status:** `COMPLETED`
**Author:** grimur & NAS Helper (AI)

## 📝 Executive Summary

Migrated the Traefik/CrowdSec/Redis/Authelia gateway stack and Cloudflare Tunnel from
OMV-managed auto-generated compose files into the GitOps-controlled `infrastructure/`
directory. All configuration is now version-controlled, reproducible, and independent of OMV.

This milestone also creates the `traefik_internal` and `traefik_tunnel` Docker networks
that all future service migrations will depend on.

## 🛠️ What We Did

1. **Created `infrastructure/gateway/`** — Full ingress + security + auth stack:
   - Traefik v3.6 (reverse proxy)
   - wollomatic/socket-proxy:1 (filtered Docker socket)
   - CrowdSec v1.7.6 (WAF / ban decisions)
   - Redis 8.6 (Authelia session store)
   - Authelia 4.39 (SSO / OIDC)

2. **Created `infrastructure/cloudflare/`** — External access stack:
   - cloudflare/cloudflared:2026.3.0 (tunnel client)
   - timothyjmiller/cloudflare-ddns:2.0.8 (DDNS for vpn.pippinn.me)

3. **Migrated config files** from `/appdata/traefik/` into the repo under
   `infrastructure/gateway/config/` — fully git-tracked.

4. **Updated `.gitignore`** — Changed `*.env` → `.env` (only files named exactly `.env`
   are ignored). `vars.env` and `global.env` are now tracked with values.

5. **Updated OMV BorgBackup exclusions** to skip CrowdSec hub-managed content
   (auto-downloaded at startup) and runtime log/data directories.

6. **Updated `ARCHITECTURE.md`** with the expanded exclusions list.

## ⚙️ Final Directory Structure

```
infrastructure/
  gateway/
    compose.yaml        ← traefik, socket-proxy, crowdsec, redis, authelia
    vars.env            ← git-tracked non-sensitive config
    .env                ← git-ignored secrets
    config/
      traefik.yml       ← static config (git-tracked)
      dynamic/
        middlewares.yml ← git-tracked
        routes.yml      ← git-tracked
      authelia/
        configuration.yml   ← git-tracked
        users_database.yml  ← git-tracked (pbkdf2 hashes only)
        secrets/            ← git-ignored (OIDC private key)
      crowdsec/
        acquis.d/       ← git-tracked (our log sources config)
        config.yaml     ← git-tracked
        profiles.yaml   ← git-tracked
        hub/            ← git-ignored (auto-downloaded)
        collections/    ← git-ignored (auto-downloaded)
        [etc.]
      acme.json         ← git-ignored (Let's Encrypt certs)
    logs/               ← git-ignored (runtime)
  cloudflare/
    compose.yaml        ← cloudflared, cloudflare-ddns
    vars.env            ← git-tracked (DDNS config: IP4_DOMAINS, TTL, etc.)
    .env                ← git-ignored (TUNNEL_TOKEN, CLOUDFLARE_API_TOKEN)
```

## ⚓ Key Decisions

- **`gateway` folder name** — The stack is more than Traefik; it's the full ingress,
  security, and auth layer. `gateway` reflects this scope.
- **`crowdsec-db` as external volume** — OMV's project name prefixed the volume as
  `traefik_crowdsec-db`. Declaring it external preserves all ban decisions and
  IP reputation data across the migration.
- **Image pinning** — All images pinned to running versions to avoid unintentional
  upgrades during cutover (traefik:v3.6, crowdsec:v1.7.6, redis:8.6-alpine,
  authelia:4.39, cloudflared:2026.3.0, cloudflare-ddns:2.0.8).
- **DDNS via env vars** — `timothyjmiller/cloudflare-ddns:2.0.8` supports
  `CLOUDFLARE_API_TOKEN` as env var. No config JSON file needed.
- **CrowdSec hub content gitignored** — `hub/`, `collections/`, `parsers/`,
  `scenarios/`, `postoverflows/`, `contexts/`, `patterns/`, `appsec-configs/`,
  `appsec-rules/` are all auto-downloaded by CrowdSec at startup. Tracking them
  would bloat the repo with hundreds of files that change with every CrowdSec update.

## 🆕 New Secrets / Variables Created

No new secrets were generated. Existing secrets were migrated from OMV env files:

| Variable | Location | Purpose |
|----------|----------|---------|
| `CLOUDFLARE_TOKEN` | `infrastructure/gateway/.env` | Traefik DNS challenge |
| `REDIS_PASSWORD` | `infrastructure/gateway/.env` | Authelia ↔ Redis |
| `AUTHELIA_JWT_SECRET` | `infrastructure/gateway/.env` | Authelia JWT signing |
| `AUTHELIA_SESSION_SECRET` | `infrastructure/gateway/.env` | Authelia session |
| `AUTHELIA_ENCRYPTION_KEY` | `infrastructure/gateway/.env` | Authelia storage |
| `TUNNEL_TOKEN` | `infrastructure/cloudflare/.env` | Cloudflare Tunnel |
| `CLOUDFLARE_API_TOKEN` | `infrastructure/cloudflare/.env` | DDNS updates |

## 📋 ARCHITECTURE.md Update Required?

**Yes — completed.** Backup exclusions section updated to reflect the new CrowdSec
hub-managed path exclusions added to the OMV BorgBackup job.

## ⚠️ Known Risks & Technical Debt

- **CrowdSec bouncer key in middlewares.yml** — The CrowdSec LAPI bouncer key is
  hardcoded in `config/dynamic/middlewares.yml` (git-tracked). It's a local-network-only
  key with no external attack surface, but ideally it would be injected at runtime.
  Acceptable risk for now.
- **Old OMV stacks** — The OMV-managed traefik/cloudflare stacks should be disabled in
  OMV UI to prevent them auto-starting after a reboot. Also remove `traefik_crowdsec-db`
  volume once confident: `docker volume rm traefik_crowdsec-db`

## 🏁 Result

The core infrastructure is now fully defined in Git. The next logical step is **Milestone 04**,
which can begin migrating individual application services (Immich, Home Assistant, etc.)
into `services/` once the gateway cutover is confirmed successful.
