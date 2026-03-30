# Milestone 07.5 Plan: WireGuard — Fix MTU Value

**Date:** 2026-03-29
**Status:** `PLANNED`

---

## Problem

All peer configs and the server config have no `MTU =` directive in their `[Interface]`
block, causing the linuxserver container to use the OS default of 1420. This is producing
slow speeds on at least two clients (`GrimurFlandri`, `GrimurPixel`/phone).

`MTU = 1280` is the safest universal value — it is the minimum IPv6 MTU and fits safely
within any transport (PPPoE, mobile, double-NAT, etc.) without fragmentation.

---

## Current State

All four peer configs and `wg0.conf` have no MTU set:

| File | Interface block | MTU present? |
|------|----------------|--------------|
| `config/wg_confs/wg0.conf` | `[Interface]` Address=10.13.13.1 | ❌ |
| `config/peer_Tryggvi/peer_Tryggvi.conf` | `[Interface]` Address=10.13.13.2 | ❌ |
| `config/peer_GrimurFlandri/peer_GrimurFlandri.conf` | `[Interface]` Address=10.13.13.3 | ❌ |
| `config/peer_GrimurPixel/peer_GrimurPixel.conf` | `[Interface]` Address=10.13.13.4 | ❌ |
| `config/peer_GrimurMacFlandri/peer_GrimurMacFlandri.conf` | `[Interface]` Address=10.13.13.5 | ❌ |
| `config/templates/server.conf` | template | ❌ |
| `config/templates/peer.conf` | template | ❌ |

---

## Fix

Add `MTU = 1280` to the `[Interface]` block in all seven files.

**Server restart:** `docker compose restart wireguard` in `infrastructure/wireguard/`.

**Peer reconnect:** Each client must re-import their updated `.conf` (or manually add
`MTU = 1280` to their local WireGuard interface settings) and reconnect.

---

## Rollback

Remove the `MTU = 1280` lines from all files and restart the wireguard container.
WireGuard will fall back to the OS default (1420).
