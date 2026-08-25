# Milestone 19: Fix Pi DNS Resolution — Summary

## What Changed

Changed the Raspberry Pi's DNS resolver from `1.1.1.1` (Cloudflare) to `192.168.86.1`
(LAN router) via NetworkManager:

```bash
nmcli connection modify "Network not found" ipv4.dns "192.168.86.1"
nmcli connection up "Network not found"
```

## Why

The Pi resolved `*.pippinn.me` via Cloudflare, returning Tunnel IPs instead of the NAS
(`192.168.86.17`). This silently broke photoframe-server's daily Immich fetch and
Uptime Kuma's host-level name resolution for `*.internal.pippinn.me`.

## Verified

| Check | Result |
|-------|--------|
| `dig +short photos.pippinn.me` | `192.168.86.17` |
| `curl -sI https://photos.pippinn.me/api/server/version` | `HTTP/2 200` |
| `getent hosts monitoring.internal.pippinn.me` | `192.168.86.17` |

## No Updates Needed

- No changes to `ARCHITECTURE.md` or `global.env`.
- No new secrets or variables created.
- Persists across reboots (NM connection profile).
