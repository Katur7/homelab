# 01 WireGuard MSS Clamping & GRO Fix

**Status:** COMPLETE (2026-04-08)

## What was changed

Added TCP MSS clamping rules to `PostUp`/`PostDown` in:
- `infrastructure/wireguard/config/wg_confs/wg0.conf` (live config, gitignored)
- `infrastructure/wireguard/config/templates/server.conf` (template, now git-tracked)

Also added `.gitignore` exception to track `config/templates/` (no secrets in templates).

## Why it was changed

**Symptom:** VPN clients could ping internet IPs (8.8.8.8) but could not browse websites. DNS worked for small UDP queries. Large HTTP/HTTPS responses failed or were intermittent.

**Root cause:** WireGuard MTU is set to 1320. Without MSS clamping, internet servers negotiate TCP MSS based on standard Ethernet MTU (1460) and send segments up to 1460 bytes. These are too large to fit through the 1320-byte WireGuard tunnel, causing fragmentation or silent drops for TCP traffic.

MSS clamping fixes this by modifying the MSS field in TCP SYN/SYN-ACK packets at connection establishment, so both sides negotiate a segment size that fits through the tunnel.

## Rules added

```
# SYN-ACK going to VPN clients — clamp to wg0 PMTU (auto-calculates from MTU 1320)
iptables -t mangle -A FORWARD -o %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu

# SYN from VPN clients going to internet — hard-set to 1280 (1320 - 40 byte IP+TCP headers)
iptables -t mangle -A FORWARD -i %i -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --set-mss 1280
```

Rules are in the **mangle table FORWARD chain** (not filter), because the existing ACCEPT rules in filter FORWARD would shadow any rules appended there.

## Notes

- No secrets created
- `ARCHITECTURE.md` does not need updating
- `wg0.conf` is gitignored — the live fix persists on disk across container restarts
- The template fix ensures future container re-generations pick up the rule

---

## Follow-up: GRO causing packet loss for ECMP-routed sites (2026-04-08)

### Symptom

After MSS clamping was applied, most sites worked. Two sites (visir.is, dv.is) remained broken in Chrome and very slow in Firefox. Other Icelandic sites (mbl.is) worked fine.

### Root cause

These sites use ECMP (equal-cost multi-path) routing on their uplinks. Consecutive TCP segments from the same flow arrive at the NAS out of TCP sequence order. GRO (Generic Receive Offload) on the physical NIC and docker bridge was combining correctly-sized 1268-byte segments into 2536-byte super-segments before they reached the WireGuard container. These super-segments exceeded the wg0 MTU (1320) and were dropped.

QUIC (HTTP/3) traffic from Chrome was affected by the same GRO combining, since QUIC uses UDP and GRO applies to UDP as well.

### Fix

Disabled GRO on all three layers:

1. **enp4s0** (physical NIC) — via `/etc/systemd/network/10-enp4s0-gro-off.link`
2. **docker bridge and veth** (all new interfaces) — via `/etc/udev/rules.d/99-docker-gro-off.rules`

Both files are deployed directly to the NAS host; not tracked in this repo.

### Verification

With GRO disabled: all 5 packets in an out-of-order burst reached the phone in a single ACK batch with no retransmits required. Chrome and Firefox both load visir.is normally including via QUIC/HTTP3.
