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
- **Source:** `/home/grimur/homelab/`
- **Destination:** Existing local Borg repository on NAS share (`/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg/`)
- **Method:** OMV BorgBackup plugin — job configured via OMV UI
- **Archive prefix:** `homelab-`
- **Schedule:** Daily at 02:00
- **Retention:** 7 daily / 4 weekly / 3 monthly
- **Exclusions:**
  - `volumes/` — Docker volume data
  - `infrastructure/gateway/logs/` — runtime access logs
  - `infrastructure/gateway/config/authelia/secrets/` — OIDC private key
  - CrowdSec hub-managed content (auto-downloaded at startup, not our config):
    - `infrastructure/gateway/config/crowdsec/hub/`
    - `infrastructure/gateway/config/crowdsec/collections/`
    - `infrastructure/gateway/config/crowdsec/parsers/`
    - `infrastructure/gateway/config/crowdsec/scenarios/`
    - `infrastructure/gateway/config/crowdsec/postoverflows/`
    - `infrastructure/gateway/config/crowdsec/contexts/`
    - `infrastructure/gateway/config/crowdsec/patterns/`
    - `infrastructure/gateway/config/crowdsec/appsec-configs/`
    - `infrastructure/gateway/config/crowdsec/appsec-rules/`
  - `.git/` backed up in full for complete history recovery

### Verify Backup Health
```bash
borg list /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg/
```
Look for recent `homelab-YYYY-MM-DD` archives.

> ⚠️ **Note:** This is a local-only backup. An offsite destination is a future milestone.