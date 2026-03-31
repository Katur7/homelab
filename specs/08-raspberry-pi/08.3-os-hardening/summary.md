# Milestone 08.3 Summary: OS Security Hardening

**Date:** 2026-03-31
**Status:** Complete

## What Was Changed

### SSH
- Disabled password authentication (`PasswordAuthentication no`)
- Disabled root login (`PermitRootLogin no`)
- Key-based login verified working before restart

### Firewall (ufw)
- Installed (`ufw` not present by default on Raspberry Pi OS)
- Allowed: 22/tcp (SSH), 53/tcp+udp (DNS), 80/tcp (PiHole UI), 3001/tcp (UptimeKuma)
- Default policy: deny incoming, allow outgoing
- Enabled and active

### fail2ban
- Installed and enabled
- SSH jail (`sshd`) active with default config — no custom jail needed

### User Audit
- `grimur` password changed to a new strong password
- Accounts with login shells: `root` (SSH blocked), `sync` (not a real shell), `grimur` — all expected
- No unexpected accounts found

## New Secrets/Variables
None — OS-level changes only.

## Architecture/global.env Updates Required
None.
