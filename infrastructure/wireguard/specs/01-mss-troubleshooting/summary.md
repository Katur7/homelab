# 07.7 WireGuard TCP MSS Clamping

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
