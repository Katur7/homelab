# Architecture Specifications

## 🖥️ Hosts

| Host | Role | LAN IP | Repo path |
|------|------|--------|-----------|
| OMV NAS | Primary host — all production services, Traefik, Cloudflare Tunnel | `192.168.86.17` | `services/`, `infrastructure/` |
| Raspberry Pi | Secondary host — backup DNS, sync, monitoring | `192.168.86.26` | `pi/` |

**NAS PiHole** (primary DNS): macvlan IP `192.168.86.27`
**Pi PiHole** (backup DNS): direct port on Pi LAN IP `192.168.86.26`

---

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

All service config and state data lives inside the service folder under `services/<service>/`.
These subdirectories are **gitignored** (binary data, secrets, large files) but covered
by the BorgBackup job which sources `/home/grimur/homelab/`.

| Type | Location | Git-tracked? | Backed up? |
|------|----------|-------------|------------|
| Compose definition | `services/<service>/compose.yaml` | ✅ Yes | ✅ Yes |
| Non-secret config | `services/<service>/vars.env` | ✅ Yes | ✅ Yes |
| Secrets | `services/<service>/.env` | ❌ No (gitignored) | ✅ Yes |
| App state / config dirs | `services/<service>/<data>/` | ❌ No (gitignored) | ✅ Yes |
| Bulk media (photos, video, books) | `/srv/dev-disk-by-uuid-<id>/` | ❌ No | ❌ Separate strategy |

## 🔒 Backup Strategy

### Homelab Repository Backup (Milestone 02)
- **Tool:** OMV BorgBackup plugin
- **Source:** `/home/grimur/homelab/`
- **Destination:** Local Borg repo on NAS share
- **Schedule:** Daily at 02:00 — retention: 7 daily / 4 weekly / 3 monthly
- **Note:** Local-only; offsite is a future milestone.

> Full details in [`specs/02-backup/`](specs/02-backup/).

## 🔧 Scripts & Tooling

### `scripts/add-dns.sh` — Add Local DNS Record
Adds an A + AAAA record for `<service>.pippinn.me` to PiHole via the v6 REST API.
Points to the NAS/Traefik gateway: IPv4 `192.168.86.17`, IPv6 `2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362`.

**Usage:**
```bash
./scripts/add-dns.sh <service-name>
# Example: ./scripts/add-dns.sh jellyfin
# → Creates jellyfin.pippinn.me → 192.168.86.17 + 2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362
```

**Password:** Set `$PIHOLE_PASSWORD` env var, or the script auto-reads `infrastructure/dns/.env`.