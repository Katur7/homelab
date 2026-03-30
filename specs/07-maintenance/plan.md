# Milestone 07 Plan: Infrastructure Maintenance & Tuneup

**Date:** 2026-03-29
**Status:** `IN PROGRESS`

---

## Overview

A maintenance pass to fix six operational issues that have accumulated since the GitOps
migration. No new services — purely stabilisation and correctness.

---

## Sub-Milestones

### 07.1 — Traefik: Full URL in Access Logs

**Problem:** `format: common` (Apache CLF) only records the path portion of the request
(e.g. `GET /dashboard HTTP/1.1`). The `RequestHost` is absent, making log analysis and
CrowdSec correlation harder.

**Fix:** Change `format: common` → `format: json` in `traefik.yml` `accesslog` block.
JSON format captures all Traefik access log fields including `RequestHost`, `RequestAddr`,
router and service names, durations, etc.

**Risk:** CrowdSec parses Traefik access logs via `crowdsecurity/traefik-logs` parser.
That parser supports both CLF and JSON. However, confirm the acquis `logtype` is set to
`file` (not `syslog`) and that CrowdSec reloads cleanly after the change.

**Files:**
- `infrastructure/gateway/config/traefik.yml` — change `accesslog.format`
- `infrastructure/gateway/config/crowdsec/acquis.d/traefik.yaml` — verify, no change expected

**Rollback:** Revert `format` back to `common`. CrowdSec will continue parsing without issue.

---

### 07.2 — WUD: Fix Tag Label False Positives

7 false positives and 2 pin-quality violations identified via WUD API audit on 2026-03-29.
Affects: `calibre-web`, `homeassistant`, `immich_machine_learning`, `immich_postgres`,
`qbittorrent`, `redis`, `sonarr`, `syncthing`, `ord_dagsins`, `matter-server`, `mealie`.

→ See [07.2-wud-tags/plan.md](07.2-wud-tags/plan.md)

---

### 07.3 — Tailscale: Activate the Service

**Problem:** `infrastructure/tailscale/` has a complete `compose.yaml` but is not running.
No `.env` exists, so `TS_AUTHKEY` is absent and the container cannot authenticate.

**What exists:**
- `compose.yaml`: `tailscale/tailscale:stable`, kernel mode (`TS_USERSPACE=false`),
  hostname `pippinn`, `/dev/net/tun` device, `net_admin` cap, `./state` volume.
- `vars.env`: `TS_STATE_DIR`, `TS_USERSPACE=false`.
- `.env`: **exists** — contains an expired/stale `TS_AUTHKEY` from the prior run (2026-03-24).
- `state/tailscaled.state`: **valid node identity present** — clean shutdown on 2026-03-24.
- `/dev/net/tun`: confirmed present on the NAS host.

**Fix:**
1. Pin image from `tailscale/tailscale:stable` → specific version (check latest at time of execution).
2. Remove `TS_AUTHKEY` from `.env` — the container entrypoint passes the key to `tailscale up`
   on every start. If the key is expired, it will fail to authenticate even though valid state
   exists. With no key set, the container reconnects using the existing `tailscaled.state`.
3. `docker compose up -d` in `infrastructure/tailscale/`.
4. Verify with `docker exec tailscale tailscale status`.
5. If status shows the node needs re-authentication (state was deleted from Tailscale admin),
   generate a new reusable auth key in the Tailscale admin console and add it back to `.env`,
   then `docker compose up -d` again.

**Risk:**
- If the node was manually removed from the Tailscale admin console, state is invalid and
  a new auth key will be required (see step 5).
- For long-term robustness, prefer OAuth client credentials over reusable keys — OAuth
  credentials never expire and are not tied to a personal user account. Only available on
  paid Tailscale plans.

**Rollback:** `docker compose down` in `infrastructure/tailscale/`. No system-level
changes are made by the container itself.

---

### 07.4 — OMV: Reduce Email Noise

Three email sources identified: BorgBackup cron completions, Fail2Ban stop/start on reboot,
and web UI login events. All suppressible via OMV notification settings + crontab.

→ See [07.4-omv-emails/plan.md](07.4-omv-emails/plan.md)

---

### 07.5 — WireGuard: Fix MTU Value

No `MTU =` set in any config. Slow speeds on `GrimurFlandri` and `GrimurPixel`.
Setting `MTU = 1280` on all 4 peers, server, and templates.

→ See [07.5-wireguard-mtu/plan.md](07.5-wireguard-mtu/plan.md)

---

### 07.6 — Home Assistant: Log Audit & Error Fix

HA logs unreviewed since Milestone 06.9. Audit for errors, deprecated config, and
integration failures. Also pins `matter-server` away from `:stable` (if not done in 07.2).

→ See [07.6-home-assistant-logs/plan.md](07.6-home-assistant-logs/plan.md)

---

| # | Sub-milestone | Risk | Restart required |
|---|---------------|------|-----------------|
| 07.1 | Traefik access log format | Low | Traefik container |
| 07.2 | WUD tag labels | Low | Affected service containers |
| 07.3 | Tailscale activation | Medium | New container start |
| 07.4 | OMV email tuning | Low | None (OMV UI only) |
| 07.5 | WireGuard MTU | Low | `wireguard` container + peer reconnects |
| 07.6 | Home Assistant log audit | Low–Medium | HA container (if config changes needed) |

---

## Open Questions

1. ~~**07.2:** Which containers are currently producing false-positive WUD alerts?~~ Resolved.
2. ~~**07.4:** What are the email subjects/frequency?~~ Resolved.
3. ~~**07.5:** What is the exact MTU problem?~~ Resolved — set MTU=1280 on all peers and server.
