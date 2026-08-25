# Milestone 19: Fix Pi DNS Resolution

## Problem

The Raspberry Pi's (`192.168.86.26`) `/etc/resolv.conf` points at `1.1.1.1` (Cloudflare).
This means host-level DNS queries resolve `*.pippinn.me` to Cloudflare Tunnel IPs
instead of the NAS (`192.168.86.17`), breaking:

1. **photoframe-server** — daily 03:00 fetch from `photos.pippinn.me` (Immich) fails silently;
   the frame holds stale image.
2. **Uptime Kuma** — `getent hosts monitoring.internal.pippinn.me` fails on the Pi host.

## Root Cause

NetworkManager manages the Pi's network. The active WiFi connection (`"Network not found"`)
has a static config with `ipv4.dns: 1.1.1.1` explicitly set.

```
ipv4.method:     manual
ipv4.dns:        1.1.1.1
ipv4.gateway:    192.168.86.1
ipv4.addresses:  192.168.86.26/24
```

## Fix

Change the DNS server from `1.1.1.1` to `192.168.86.1` (LAN router, which forwards to
PiHole on NAS `192.168.86.27` + Pi `192.168.86.26`). No fallback DNS — failures should
be loud, not silently wrong.

```bash
nmcli connection modify "Network not found" ipv4.dns "192.168.86.1"
nmcli connection up "Network not found"
```

This persists across reboots (NM connection profile is stored on disk).

## Why `192.168.86.1` (option C)

| Option | Target | Rejected because |
|--------|--------|-----------------|
| A | `127.0.0.1` (Pi's own PiHole) | If PiHole container crashes, Pi loses all DNS |
| B | `192.168.86.27` (NAS PiHole) | Pi DNS breaks if NAS is down |
| **C** | **`192.168.86.1` (router)** | **Selected** — same resolver the rest of the LAN uses |

## Verification

Run on the Pi after applying:

```bash
dig +short photos.pippinn.me                              # expect 192.168.86.17
curl -sI https://photos.pippinn.me/api/server/version     # expect 200
getent hosts monitoring.internal.pippinn.me                # expect 192.168.86.17
```

## Rollback

```bash
nmcli connection modify "Network not found" ipv4.dns "1.1.1.1"
nmcli connection up "Network not found"
```

## Impact

- No service restarts needed — containers use Docker's internal DNS, not the host resolver.
- photoframe-server's next 03:00 run should succeed automatically.
- Uptime Kuma host-level name resolution will work.
