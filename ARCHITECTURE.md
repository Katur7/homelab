# Architecture Specifications

## 🔑 Environment Strategy
Each service folder must contain:
1. `compose.yaml`: The service definition.
2. `vars.env`: Non-sensitive config (Tracked in Git).
3. `.env`: Secrets/Passwords (Ignored by Git).

All services must reference `../../global.env` for shared variables.

## 🌐 Networking & DNS
- **External:** `https://<service>.pippinn.me` (Routed via Cloudflare Tunnel -> Traefik).
- **Internal:** `https://<service>.internal.pippinn.me` (Local DNS via PiHole -> Traefik).
- **Traefik v3:** All routing uses Traefik v3 labels with backtick syntax.
- **Isolation:** Apps use a backend bridge network for DB communication. Only Traefik/Tunnels inhabit the `traefik_tunnel` network.

## 💾 Volume Management
- **Configs:** Stored locally in `./config` within the service folder for portability.
- **Bulk Data:** Absolute paths to OMV-managed RAID/HDD shares (e.g., `/srv/dev-disk-...`).
- **Permissions:** All containers should use `PUID=1000` and `PGID=1000` to match user `grimur`.