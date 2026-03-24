# Milestone 04 Summary: PiHole DNS Infrastructure

**Date:** 2026-03-24
**Status:** `COMPLETED`
**Author:** grimur & NAS Helper (AI)

## 📝 Executive Summary

Migrated the NAS PiHole instance from OMV-managed compose (`/appdata/pihole/pihole.yml`)
into the GitOps-controlled `infrastructure/dns/` directory. Configuration is now
version-controlled and independently manageable.

The Pi PiHole (192.168.86.26) remains as a replica managed separately on the Pi.
nebula-sync on the Pi continues to sync from the NAS (PRIMARY) unchanged.

## 🛠️ What We Did

1. **Created `infrastructure/dns/`** — PiHole v6 stack:
   - `pihole/pihole:2026.02.0` on macvlan (`enp4s0`) with dedicated LAN IP 192.168.86.27
   - Dual network: `pihole_network` (macvlan for DNS) + `traefik_internal` (for web UI)
   - Traefik labels for web UI at `pihole.internal.pippinn.me`

2. **Migrated config volume** from `/appdata/pihole/config/` → `infrastructure/dns/config/`
   (fully gitignored — all runtime state: gravity.db, pihole.toml, logs)

3. **Updated `.gitignore`** — added `/infrastructure/dns/config/`

4. **Updated `ARCHITECTURE.md`** — added `pihole_network` to network overview and
   documented the Traefik entrypoint/middleware reference table:
   - `websecure` (internal): `internal-only` IP allowlist applied globally, no Authelia
   - `tunnel` (external): `external-no-auth-chain` (CrowdSec + rate-limit) applied globally;
     services requiring Authelia must add `authelia-auth@file` middleware explicitly

## ⚙️ Final Directory Structure

```
infrastructure/
  dns/
    compose.yaml        ← pihole container (macvlan + traefik_internal)
    vars.env            ← git-tracked: FTLCONF_* env vars, PIHOLE_UID/GID
    .env                ← git-ignored: FTLCONF_WEBSERVER_API_PASSWORD
    config/             ← git-ignored: runtime state (gravity.db, logs, etc.)
```

## ⚓ Key Decisions

- **macvlan (`pihole_network`)** — PiHole keeps its dedicated LAN IP 192.168.86.27.
  No port mapping needed; DNS accessible directly at that IP. Parent interface: `enp4s0`.
- **IPv6 macvlan** — Google WiFi doesn't support the link-local gateway, so IPv6 gateway
  is omitted (same limitation as the OMV compose). Preserved as-is.
- **`pihole_network` defined here** (not external) — this stack owns the macvlan definition,
  same as the OMV compose.
- **Config volume fully gitignored** — PiHole v6 stores all state (adlists, custom DNS,
  whitelist, gravity.db) in SQLite. nebula-sync handles replication to the Pi replica.
- **`PIHOLE_UID/GID` in `vars.env`** — PiHole v6 uses these instead of `PUID/PGID`.
  Hardcoded to `1000`/`100` (matches system user) rather than referencing `global.env`
  (env_file does not support variable interpolation).
- **`dnsmasq.d/` not mounted** — legacy from PiHole v5. The wildcard DNS rule
  `address=/.internal.pippinn.me/192.168.86.17` is set via `FTLCONF_misc_dnsmasq_lines`.

## 🆕 New Secrets / Variables Created

| Variable | Location | Purpose |
|----------|----------|---------|
| `FTLCONF_WEBSERVER_API_PASSWORD` | `infrastructure/dns/.env` | PiHole web UI password |

No new secrets generated — password migrated from hardcoded value in OMV compose.

## 📋 ARCHITECTURE.md Update Required?

**Yes — completed.** Added `pihole_network` to network overview and documented the
internal service authentication pattern (websecure = internal-only IP allowlist only).

## ⚠️ Known Considerations

- **DNS records not git-tracked** — Custom DNS entries (e.g. `todo.pippinn.me`) are added
  via the PiHole web UI and stored in `gravity.db`. nebula-sync replicates them to the Pi.
  Git tracks the deployment definition only, not individual DNS records. A future milestone
  could introduce a git-tracked dnsmasq override file if this becomes a pain point.
- **nebula-sync** — Runs on the Pi, syncing FROM the NAS (PRIMARY). Reconnected
  automatically after cutover with no configuration changes needed.

## 🏁 Result

PiHole DNS infrastructure is now fully defined in Git. The next logical step is
**Milestone 05** (WUD, Tailscale, WireGuard — remaining infrastructure services).
