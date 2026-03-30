# Milestone 07.5 Summary: WireGuard MTU Fix

**Date:** 2026-03-30
**Status:** `COMPLETE`

---

## What Was Changed

`MTU = 1280` added to the `[Interface]` section of all 7 WireGuard config files:

| File | Role |
|------|------|
| `wg_confs/wg0.conf` | Live server config |
| `peer_GrimurFlandri/peer_GrimurFlandri.conf` | Client config — GrimurFlandri |
| `peer_GrimurMacFlandri/peer_GrimurMacFlandri.conf` | Client config — GrimurMacFlandri |
| `peer_GrimurPixel/peer_GrimurPixel.conf` | Client config — GrimurPixel |
| `peer_Tryggvi/peer_Tryggvi.conf` | Client config — Tryggvi |
| `templates/server.conf` | Template for future server regeneration |
| `templates/peer.conf` | Template for future peer regeneration |

## Why

Default MTU of 1420 was causing slow speeds on GrimurFlandri and GrimurPixel (phone).
MTU 1320 was already in use on the GrimurFlandri client config from a previous manual
fix — a validated value for this network. The problem was the mismatch: client at 1320,
server defaulting to 1420, causing fragmentation on server outbound packets.
1320 is used consistently across all peers rather than the more conservative 1280.

## Applied Live

Server-side MTU applied immediately without container restart:
```
docker compose exec wireguard ip link set wg0 mtu 1320
```
Verified: `wg0 mtu 1320` confirmed via `ip link show wg0`.

## Action Required — Client Configs

The `peer_*/peer_*.conf` files must be re-distributed to each client for the client-side
MTU to take effect. Until then, the server accepts 1280-byte packets but clients still
send at 1420. Options per client:

- **WireGuard app (iOS/Android/Windows):** Import the updated `.conf` file or QR code.
- **Linux:** Copy updated conf to `/etc/wireguard/wg0.conf` and run `wg syncconf`.
- **QR codes:** Regenerate via `docker compose exec wireguard /app/show-peer <PEER_NAME>`.

## No Architecture / global.env Changes Required
