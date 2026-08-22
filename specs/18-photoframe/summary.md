# Milestone 18: Register Photoframe Stack on Pi — Summary

## What was done

Registered the photoframe service (ESP32-S3 photo frame HTTP server on the Pi) in the homelab repo. The stack itself lives in [photoframe-server](https://github.com/Katur7/photoframe-server) at `~/photoframe-server` on the Pi.

## DNS — Route 1 won

Added a PiHole local DNS host record via the API (`scripts/add-dns.sh` pattern). A host record **beats** the `address=` wildcard for the same domain — tested and confirmed. Nebula-sync carried the record to the Pi PiHole within 5 minutes (`SYNC_CONFIG_DNS=true`).

No `vars.env` changes were needed. The record lives in PiHole's config, not in the dnsmasq env var.

**Verification (all three return `192.168.86.26`):**

| Resolver | Result |
|----------|--------|
| NAS PiHole (`@192.168.86.27`) | `192.168.86.26` |
| Pi PiHole (`@192.168.86.26`) | `192.168.86.26` |
| Default resolver | `192.168.86.26` |

**Precedence rule for future services:** A PiHole local DNS host record overrides an `address=` wildcard for the same domain. No need for a more-specific `address=` line (Route 2). Use the API or `add-dns.sh` pattern.

## TZ mismatch — resolved

Pi host `/etc/timezone` said `Europe/London` while `pi/global.env` and all containers use `Europe/Stockholm`. Fixed with `timedatectl set-timezone Europe/Stockholm` on the Pi. The weekly cron now fires at 03:00 Stockholm (was 03:00 London = 04:00 Stockholm), no longer overlapping with the photoframe's 04:00 wake window.

## Files changed

| File | Change |
|------|--------|
| `pi/services/photoframe/README.md` | New — documentation-only service entry |
| `pi/README.md` | Photoframe added to services table and repo layout |
| `pi/scripts/update-containers.sh` | Comment explaining photoframe exclusion from STACKS |
| `specs/18-photoframe/plan.md` | Milestone plan |
| `specs/18-photoframe/summary.md` | This file |

## New secrets / variables

None.

## ARCHITECTURE.md / global.env updates required

None.

## Known issues noted but not addressed

- **Sync canary** (`sync-verify.internal.pippinn.me`) — resolves via wildcard regardless of whether sync has run. The Uptime Kuma monitor for it is unfalsifiable. Worth its own item.
- **Pi cannot resolve internal names from the host** — `/etc/resolv.conf` points at `1.1.1.1`. Separate issue.
