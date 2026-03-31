# Milestone 08 Summary: Raspberry Pi — Documentation, Hardening & Maintenance

**Date:** 2026-03-31
**Status:** Complete

## What Was Done

| Sub-milestone | Outcome |
|---------------|---------|
| 08.1 — Publish repo | Repo audited and published publicly on GitHub |
| 08.2 — Pi repo structure | Pi services brought into GitOps-Lite; data migrated from `/appdata/` |
| 08.3 — OS hardening | SSH key-only, ufw firewall, fail2ban, password audit |
| 08.4 — unattended-upgrades | Security patches auto-apply; reboots at 3am if needed |
| 08.5 — Docker auto-updates | Weekly cron pulls and restarts updated containers |

## Notable Deviations from Plan

- **08.4 auto-reboot:** Plan said `false`; changed to `true` with `Automatic-Reboot-Time "03:00"`. Unpatched kernels on a persistent host are a worse risk than overnight UptimeKuma false positives.
- **08.2 nebula-sync SYNC_CONFIG_MISC:** Disabled due to `FTLCONF_misc_privacylevel=3` being env-locked on the Pi. `misc.dnsmasq_lines` (wildcard DNS for `*.internal.pippinn.me`) added to `vars.env` instead.

## New Secrets/Variables Created

| Variable | File | Purpose |
|----------|------|---------|
| `PIHOLE_PASSWORD` | `pi/services/pihole/.env` | PiHole admin password — used by nebula-sync to authenticate to both instances |

## Architecture/global.env Updates Required
None — `ARCHITECTURE.md` already documented the Pi host prior to this milestone.
