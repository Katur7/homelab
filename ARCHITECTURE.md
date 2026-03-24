# Architecture Specifications

## 🔑 Environment Strategy
Each service folder must contain:
1. `compose.yaml`: The service definition.
2. `vars.env`: Non-sensitive config (Tracked in Git).
3. `.env`: Secrets/Passwords (Ignored by Git).

All services must reference `../../global.env` for shared variables.

## 🌐 Networking & DNS
- **Tunnel Network:** `traefik_tunnel` (Defined in `infrastructure/gateway/`). Used by Cloudflare Tunnel and Traefik.
- **Internal Network:** `traefik_internal` (Defined in `infrastructure/gateway/`). Used by Traefik to communicate with services.
- **PiHole Network:** `pihole_network` (Defined in `infrastructure/dns/`). macvlan on `enp4s0` — gives PiHole a dedicated LAN IP (192.168.86.27).
- **External:** `https://<service>.pippinn.me`
- **Internal:** `https://<service>.internal.pippinn.me`
- **Traefik v3:** All routing uses Traefik v3 labels with backtick syntax.

### Traefik Entrypoints & Middleware

| Entrypoint | Port | Used for | Default middleware chain |
|------------|------|----------|--------------------------|
| `websecure` | 443 | Internal services (`*.internal.pippinn.me`) | `internal-only` (IP allowlist: LAN + traefik_internal) |
| `tunnel` | 8443 | External services via Cloudflare Tunnel | `external-no-auth-chain` (CrowdSec + rate-limit) |

**Internal services** (`websecure` only):
- The `internal-only` middleware is applied **globally** to `websecure` in `traefik.yml`
- No explicit middleware label needed on individual service containers
- Never added to the `tunnel` entrypoint — not reachable externally
- Not protected by Authelia

**External services** (both `websecure` + `tunnel`):
- Default middleware on `tunnel` is `external-no-auth-chain` (CrowdSec + rate-limit)
- To require Authelia login, add `authelia-auth@file` explicitly as an additional middleware label
- Must be explicitly added to the `tunnel` entrypoint via a label

## 💾 Volume Management
- **Configs:** Stored locally in `./config` within the service folder for portability.
- **Bulk Data:** Absolute paths to OMV-managed shares (e.g., `/srv/dev-disk-by-uuid-...`).
- **Permissions:** All containers should use `PUID=1000` and `PGID=100` (User: grimur, Group: users).

## 🔒 Backup Strategy

### Homelab Repository Backup (Milestone 02)
- **Tool:** OMV BorgBackup plugin
- **Source:** `/home/grimur/homelab/`
- **Destination:** Local Borg repo on NAS share
- **Schedule:** Daily at 02:00 — retention: 7 daily / 4 weekly / 3 monthly
- **Note:** Local-only; offsite is a future milestone.

> Full details in [`specs/02-backup/`](specs/02-backup/).