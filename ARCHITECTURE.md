# Architecture Specifications

## 🔑 Environment Strategy
Each service folder must contain:
1. `compose.yaml`: The service definition.
2. `vars.env`: Non-sensitive config (Tracked in Git).
3. `.env`: Secrets/Passwords (Ignored by Git).

All services must reference `../../global.env` for shared variables.

## 🌐 Networking & DNS
- **Tunnel Network:** `traefik_tunnel` (Defined in Infrastructure/Traefik). Used by Cloudflare Tunnel and Traefik.
- **Internal Network:** `traefik_internal` (Defined in Infrastructure/Traefik). Used by Traefik to communicate with services.
- **External:** `https://<service>.pippinn.me`
- **Internal:** `https://<service>.internal.pippinn.me`
- **Traefik v3:** All routing uses Traefik v3 labels with backtick syntax.

## 💾 Volume Management
- **Configs:** Stored locally in `./config` within the service folder for portability.
- **Bulk Data:** Absolute paths to OMV-managed shares (e.g., `/srv/dev-disk-by-uuid-...`).
- **Permissions:** All containers should use `PUID=1000` and `PGID=100` (User: grimur, Group: users).