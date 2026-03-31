# Milestone 08.4 Summary: OS Auto-Updates (unattended-upgrades)

**Date:** 2026-03-31
**Status:** Complete

## What Was Changed

- Installed `unattended-upgrades` and `apt-listchanges`
- Configured `/etc/apt/apt.conf.d/50unattended-upgrades`:
  - `Automatic-Reboot "true"` — kernel patches apply automatically (plan originally said false; changed after review — unpatched kernels on a LAN host are a worse risk than overnight false-positive UptimeKuma alerts)
  - `Automatic-Reboot-Time "03:00"` — reboots at 3am if required
  - `Remove-Unused-Dependencies "true"`
  - `Mail "root"`
- Origins-Pattern: default Debian-Security + Raspbian entries already present, no changes needed
- Dry run passed cleanly — `upgrade result: True`
- `apt-daily-upgrade.timer` confirmed active

## Deviation from Plan
Auto-reboot enabled (plan said disabled). Rationale: kernel patches must reboot to take effect; manual reboots are easy to forget. 3am reboot window on a LAN-only host is acceptable.

## New Secrets/Variables
None.

## Architecture/global.env Updates Required
None.
