# Architecture Specifications

## 🖥️ Hosts

| Host | Role | Hardware / Specs | LAN IP | Repo path |
|------|------|------------------|--------|-----------|
| Debian NAS (`pippinn`) | Primary host — all production services, Traefik, Cloudflare Tunnel | Intel N150 (4C/4T), 32GB DDR4, 1TB NVMe | `192.168.86.17` | `services/`, `infrastructure/` |
| Raspberry Pi | Secondary host — backup DNS, sync, monitoring hub | Raspberry Pi 4 (4GB) | `192.168.86.26` | `pi/` |
| Backup Pi | Offsite backup target (parents' house, Tailscale-only) | Raspberry Pi | `100.110.206.9` | — |

**NAS PiHole** (primary DNS): macvlan IP `192.168.86.27`  
**Pi PiHole** (backup DNS): direct port on Pi LAN IP `192.168.86.26`  
**Immich ML** (local inference): `http://immich-machine-learning:3003` — hosted locally on NAS with Intel OpenVINO iGPU acceleration (`/dev/dri`) and NVMe model cache  
**Plex Transcoding** (hardware acceleration): Intel QuickSync via `/dev/dri` with dedicated 4GB RAM `tmpfs` transcode buffer (`/transcode`)  
**Beszel Hub** (system & S.M.A.R.T. monitoring): `http://192.168.86.26:8090` — exposed via Traefik at `monitoring.internal.pippinn.me`; agents on Pi and NAS (`SYS_RAWIO` drive monitoring)  
**Dozzle** (container logs & lifecycle): `https://logs.internal.pippinn.me` — real-time container log dashboard and container action manager on NAS (hardened via gateway `socket-proxy`); connected to Dozzle agent on Raspberry Pi (`192.168.86.26:7007`, hardened via local `socket-proxy`) for unified multi-host monitoring  

---

## 🗄️ Storage Architecture (MergerFS & SnapRAID)

The NAS uses a hybrid JBOD pool with disk-level parity protection:

```
[Physical Disks]
  ├── /srv/disk1    (3TB WD Red - Data)  ──┐
  ├── /srv/disk2    (3TB WD Red - Data)  ──┼──> MergerFS Pool: /mnt/storage
  ├── /srv/disk3    (3TB WD Red - Data)  ──┘    (atomic hardlinks for Starr apps, Samba shares)
  └── /srv/parity1  (3TB WD Red - Parity) ────> SnapRAID Parity (Excluded from MergerFS)
```

- **MergerFS Pool (`/mnt/storage`):** Pools underlying ext4 data disks with `category.create=mfs` (most free space). Enables cross-directory atomic hardlinks across downloads and media libraries.
- **SnapRAID Parity Protection:**
  - Parity stored on `/srv/parity1/snapraid.parity`. Content lists on NVMe root SSD and data disks.
  - Excludes dynamic databases, thumbnails, caches, and Borg backup repositories (`/backup/borg2/`).
  - **Automated Sync & Scrub:** Managed via systemd timers (`snapraid-sync.timer` daily at 04:00, `snapraid-scrub.timer` Sundays at 05:00) with mount-safety checks and deletion thresholds.

---

## 🔑 Environment Strategy

Each service folder contains:
1. `compose.yaml`: The service definition.
2. `vars.env`: Non-sensitive configuration (Tracked in Git).
3. `.env`: Secrets/Passwords (Ignored by Git).

All services reference `../../global.env` for shared host variables (`PUID=1000`, `PGID=1000`, `TZ=Europe/Stockholm`, `DOMAIN`).

---

## 🌐 Networking & DNS

- **Tunnel Network:** `traefik_tunnel` (Defined in `infrastructure/gateway/`). Used by Cloudflare Tunnel and Traefik.
- **Internal Network:** `traefik_internal` (Defined in `infrastructure/gateway/`). Used by Traefik to communicate with services.
- **PiHole Network:** `pihole_network` (Defined in `infrastructure/dns/`). macvlan on host NIC — gives PiHole a dedicated LAN IP (`192.168.86.27`).
- **External Routing:** `https://<service>.pippinn.me` (via Cloudflare Tunnel)
- **Internal Routing:** `https://<service>.internal.pippinn.me` (via Traefik `websecure` with local IP allowlist)
- **Traefik v3:** All routing uses Traefik v3 labels with backtick syntax.

### Traefik Entrypoints & Middleware

| Entrypoint | Port | Used for | Default middleware chain |
|------------|------|----------|--------------------------|
| `websecure` | 443 | Internal services (`*.internal.pippinn.me`) | `internal-only` (IP allowlist: LAN + traefik_internal) |
| `tunnel` | 8443 | External services via Cloudflare Tunnel | `external-no-auth-chain` (CrowdSec + rate-limit) |

**Internal services** (`websecure` only):
- The `internal-only` middleware is applied **globally** to `websecure` in `traefik.yml`.
- Protected by Authelia via `authelia-auth@file` forward-auth middleware where required.

**External services** (both `websecure` + `tunnel`):
- Default middleware on `tunnel` is `external-no-auth-chain` (CrowdSec + rate-limit).
- To require Authelia login, add `authelia-auth@file` explicitly as an additional middleware label.

---

## 💾 Volume Management

Service configuration and application state live inside each service directory under `services/<service>/`.
Subdirectories holding mutable state are **gitignored** but covered by BorgBackup.

| Type | Location | Git-tracked? | Backed up? |
|------|----------|-------------|------------|
| Compose definition | `services/<service>/compose.yaml` | ✅ Yes | ✅ Yes |
| Non-secret config | `services/<service>/vars.env` | ✅ Yes | ✅ Yes |
| Secrets | `services/<service>/.env` | ❌ No (gitignored) | ✅ Yes |
| App state / config dirs | `services/<service>/<data>/` | ❌ No (gitignored) | ✅ Yes |
| Bulk media & downloads | `/mnt/storage/{movies,tv,photos,downloads}` | ❌ No | Photos backed up to Borg; media protected by SnapRAID |

---

## 🔒 Backup Strategy

Two-tier Borg backup architecture with `repokey-blake2` encryption (passphrase in `/root/.borg-passphrase`):

| Tier | Tool / Script | Destination | Schedule | Sources |
|------|---------------|-------------|----------|---------|
| Local | `infrastructure/backup/backup-local.sh` | Borg repo on NAS (`/mnt/storage/backup/borg2`) | Daily 02:00 (`homelab`)<br>Mon 03:00 (`photos`) | `homelab/` configs & state + Immich photos |
| Offsite | `infrastructure/backup/backup-to-pi.sh` | `pi-backup` via Tailscale | Weekly Sun 04:00 | `homelab/` configs & state + Immich photos |

- **Local Homelab Retention:** 14 daily / 8 weekly / 12 monthly
- **Local Photos Retention:** 8 weekly / 12 monthly / 2 yearly
- **Heartbeat & Alerts:** Pings Uptime Kuma push monitors on success; sends email alerts via `NOTIFY_EMAIL` on failure.
- Full details, exclusions, and restore procedures in [`infrastructure/backup/`](infrastructure/backup/).

---

## 🔧 Scripts & Automation

Operational and maintenance scripts are organized under `scripts/`:

### Core Maintenance Suites (`scripts/setup/`)

| Suite | Setup Script | Deployed Timers / Services | Purpose |
|-------|--------------|----------------------------|---------|
| **SnapRAID** | `scripts/setup/snapraid/setup.sh` | `snapraid-sync.timer` (04:00)<br>`snapraid-scrub.timer` (Sun 05:00) | Nightly parity sync with deletion threshold checks & weekly scrub |
| **Borg Backup** | `scripts/setup/borg/setup.sh` | `borg-backup-local-homelab.timer` (02:00)<br>`borg-backup-local-photos.timer` (Mon 03:00)<br>`borg-backup-offsite.timer` (Sun 04:00) | Local and offsite encrypted snapshot backups |
| **Docker** | `scripts/setup/docker/setup.sh` | `docker-prune.timer` (Sun 03:30)<br>`homelab-containers.service` | Weekly unused image/build pruning & host reboot container lifecycle |
| **WireGuard** | `scripts/setup/wireguard/setup.sh` | `wireguard-uptime.timer` (Every 5m) | Container and interface health push monitoring to Uptime Kuma |

### Operational Utilities

- **`scripts/add-dns.sh`:** Adds an A + AAAA record for `<service>.pippinn.me` to PiHole via the REST API.
- **`scripts/homelab-up.sh` / `scripts/homelab-down.sh`:** Restores or shuts down all running Docker Compose stacks in dependency order.
- **`scripts/snapraid-sync.sh` / `scripts/snapraid-scrub.sh`:** Core SnapRAID automation scripts executed by systemd timers.