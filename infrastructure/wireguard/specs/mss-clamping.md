# WireGuard TCP MSS Clamping

**Added:** 2026-04-08 | **Milestone:** 07.7

## Problem

With `MTU = 1320` on wg0, VPN clients could ping internet IPs but could not browse
websites. DNS (small UDP) worked; HTTPS (large TCP) failed silently.

**Root cause:** No MSS clamping. Internet servers negotiate TCP MSS based on standard
Ethernet MTU (1460 bytes) and send segments that are too large for the 1320-byte tunnel.
Packets get fragmented or dropped.

## Fix

Two rules added to `PostUp`/`PostDown` in `wg_confs/wg0.conf` and `templates/server.conf`:

```
# SYN-ACK to VPN clients — auto-clamp based on wg0 PMTU
iptables -t mangle -A FORWARD -o %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# SYN from VPN clients to internet — hard-set MSS = 1320 - 40 (IP+TCP headers) = 1280
iptables -t mangle -A FORWARD -i %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1280
```

Rules go in the **mangle table**, not filter. The existing `ACCEPT` rules in filter FORWARD
are evaluated first and would shadow any rules appended there.

## Why mangle table works

Netfilter hook order: `mangle PREROUTING → filter FORWARD → mangle POSTROUTING`

The mangle FORWARD chain runs before the filter FORWARD chain, so TCPMSS modification
happens before the packet hits the ACCEPT rules.
