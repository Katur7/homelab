# M17 NAS Hardware & OS Migration Plan

## 1. Architectural Decisions

| Decision Area | Selected Strategy | Rationale |
| :--- | :--- | :--- |
| **Migration Approach** | **2-Phase Migration (Swap first, M.2 NVMe fresh OS)** | Isolates hardware validation from OS configuration. The existing Plextor SSD serves as a 100% working fallback during the transition. |
| **Base Operating System** | **Debian 12 (Bookworm) Minimal / Server** | Zero hypervisor tax, ~150MB idle RAM, direct access to Intel QuickSync GPU (`/dev/dri`), maximum stability for Docker GitOps. |
| **Storage Architecture** | **MergerFS + SnapRAID** | Pools data drives into `/mnt/storage` for unified capacity and atomic hardlinks for Starr apps, while preserving disk-level SnapRAID parity protection. |
| **Docker Management UI** | **Komodo** | GitOps-native, modern mobile-friendly web UI for restarting/monitoring containers, and multi-node support (manages both NAS and Raspberry Pi). |
| **Drive Health & Alerts** | **Scrutiny (Docker)** | Provides a modern web UI for S.M.A.R.T. disk attributes and automated push alerts (Discord, Telegram, or Email) on drive degradation. |

---

## 2. Storage Architecture: MergerFS + SnapRAID

### 2.1 Disk Layout

| Disk / Device | Model | Size | Mount Point | Role |
| :--- | :--- | :--- | :--- | :--- |
| **NVMe 1** (M.2) | PCIe Gen3/4 NVMe | ≥250GB | `/` | OS, Docker engine, Homelab Git repo, app data |
| **SATA 1** | Plextor PX-256M6S | 256GB | *(Detached/Spare)* | Offline fallback backup of previous OMV installation |
| **SATA 2** | WD WD30EZRX | 3TB | `/srv/disk1` | Data disk 1 (SnapRAID data + MergerFS pool member) |
| **SATA 3** | WD WD30EZRX | 3TB | `/srv/disk2` | Data disk 2 (SnapRAID data + MergerFS pool member) |
| **SATA 4** | WD WD30EZRX | 3TB | `/srv/disk3` | Data disk 3 (SnapRAID data + MergerFS pool member) |
| **SATA 5** | WD WD30EZRX | 3TB | `/srv/parity1` | SnapRAID parity disk (Excluded from MergerFS) |

### 2.2 MergerFS Configuration (`/etc/fstab`)

Install MergerFS:
```bash
sudo apt update && sudo apt install -y mergerfs
```

Add the underlying disks and the unified pool to `/etc/fstab`:
```text
# Underlying physical drives (mount by UUID)
UUID=<UUID-DISK1>   /srv/disk1    ext4   defaults,noatime   0 2
UUID=<UUID-DISK2>   /srv/disk2    ext4   defaults,noatime   0 2
UUID=<UUID-DISK3>   /srv/disk3    ext4   defaults,noatime   0 2
UUID=<UUID-PARITY>  /srv/parity1  ext4   defaults,noatime   0 2

# MergerFS Unified Storage Pool
/srv/disk*          /mnt/storage  fuse.mergerfs  defaults,nonempty,allow_other,use_ino,cache.files=partial,category.create=mfs,minfreespace=50G  0 0
```

> **Policy `category.create=mfs` (Most Free Space):** Writes new files to whichever physical drive currently has the most free space.

### 2.3 Unified Directory Structure & Atomic Hardlinks

All shared storage will live under `/mnt/storage/`:
```text
/mnt/storage/
├── media/
│   ├── movies/
│   ├── tv/
│   ├── books/
│   └── audiobooks/
├── downloads/
│   ├── complete/
│   └── incomplete/
├── photos/
└── backup/
```

> [!TIP]
> **Starr Hardlink Optimization:** By mounting `/mnt/storage:/data` across Radarr, Sonarr, and your download client, completed torrents are imported via instantaneous zero-copy hardlinks instead of slow disk-to-disk copies.

---

## 3. Management Services (Komodo & Scrutiny)

### 3.1 Komodo (Docker UI & Multi-Node Manager)

Add `services/komodo/compose.yaml`:
```yaml
name: komodo

services:
  komodo-core:
    image: ghcr.io/mbecker20/komodo-core:latest
    container_name: komodo-core
    restart: unless-stopped
    env_file:
      - ../../global.env
      - vars.env
      - .env
    volumes:
      - ./data:/etc/komodo
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - traefik_internal
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_internal"
      - "traefik.http.routers.komodo.rule=Host(`komodo.internal.pippinn.me`)"
      - "traefik.http.routers.komodo.entrypoints=websecure"
      - "traefik.http.services.komodo.loadbalancer.server.port=9120"

networks:
  traefik_internal:
    external: true
```
*Note: A Komodo Periphery agent can also be added to `pi/services/` to manage the Raspberry Pi containers from the same UI.*

### 3.2 Scrutiny (S.M.A.R.T. Drive Health & Alerting)

Add `services/scrutiny/compose.yaml`:
```yaml
name: scrutiny

services:
  scrutiny:
    image: ghcr.io/analogj/scrutiny:master-omnibus
    container_name: scrutiny
    restart: unless-stopped
    privileged: true
    cap_add:
      - SYS_RAWIO
      - SYS_ADMIN
    volumes:
      - /run/udev:/run/udev:ro
      - ./config:/opt/scrutiny/config
      - ./influxdb:/opt/scrutiny/influxdb
    devices:
      - /dev/sda
      - /dev/sdb
      - /dev/sdc
      - /dev/sdd
      - /dev/nvme0n1
    networks:
      - traefik_internal
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_internal"
      - "traefik.http.routers.scrutiny.rule=Host(`scrutiny.internal.pippinn.me`)"
      - "traefik.http.routers.scrutiny.entrypoints=websecure"
      - "traefik.http.services.scrutiny.loadbalancer.server.port=8080"

networks:
  traefik_internal:
    external: true
```

---

## 4. Step-by-Step Execution Plan

### Phase 1: Physical Hardware Swap & Validation (Existing SSD)

1. **Pre-flight on old hardware:**
   * Run Borg backup / ensure offsite Pi backup is fresh.
   * Install Intel microcode in advance: `sudo apt install -y intel-microcode`
   * Clean shutdown: `sudo poweroff`
2. **Assembly:**
   * Install generic N150 motherboard, RAM, and CPU cooler into Fractal Node 304.
   * Connect 24-pin ATX + 4-pin CPU power.
   * Connect Plextor SATA SSD (Port 1) and 4x HDDs (Ports 2–5).
   * Connect LAN cable to Port 1 (Intel i226-V).
3. **First Boot & BIOS Check:**
   * Attach monitor + keyboard.
   * Verify 16GB RAM detected in BIOS.
   * Set SATA mode to **AHCI**.
   * Set Plextor SSD as primary boot drive.
4. **Boot Validation:**
   * Boot existing Debian/OMV installation.
   * Check networking (`ip a`). If interface name changed, run `omv-firstaid` to assign IP `192.168.86.17`.
   * Verify all Docker containers start cleanly.
   * Run system stability / thermal check for 24–48 hours.

---

### Phase 2: Clean Debian 12 Install on M.2 NVMe

1. **OS Installation:**
   * Insert new M.2 NVMe SSD into the motherboard.
   * Flash Debian 12 Netinst to USB.
   * Install standard Debian 12 Minimal (SSH server + standard system utilities only).
2. **Base Configuration:**
   * Configure static IP (`192.168.86.17`) on primary 2.5GbE interface.
   * Install Docker, Docker Compose plugin, Git, MergerFS, SnapRAID, and Samba:
     ```bash
     sudo apt update && sudo apt install -y curl git mergerfs snapraid samba smartmontools
     curl -fsSL https://get.docker.com | sh
     ```
   * Add user `grimur` to `docker` and `sudo` groups.
3. **Storage & Mounts:**
   * Create mount points: `/srv/disk1`, `/srv/disk2`, `/srv/disk3`, `/srv/parity1`, `/mnt/storage`.
   * Populate `/etc/fstab` with drive UUIDs and MergerFS pool.
   * Recreate `/etc/snapraid.conf` pointing to `/srv/disk*` and `/srv/parity1`.
4. **GitOps Deployment:**
   * Clone repo to `/home/grimur/homelab`.
   * Restore `.env` files from Borg backup.
   * Update `services/*/compose.yaml` paths to point to `/mnt/storage/...` instead of individual disk UUIDs.
   * Run `./scripts/homelab-up.sh`.

---

### Phase 3: Post-Migration Enhancements

1. **Move Immich ML back to NAS (Reverse Spec 10):**
   * The Intel N150 has AVX2 (x86-64-v3) support.
   * Update `services/immich/compose.yaml` to run `immich-machine-learning` locally with CPU/iGPU acceleration.
   * Turn off remote ML container on the Raspberry Pi to free up Pi memory and CPU.
2. **Enable Intel QuickSync (QSV) Hardware Transcoding in Plex:**
   * Pass `/dev/dri` into `services/plex/compose.yaml`:
     ```yaml
     devices:
       - /dev/dri:/dev/dri
     ```
   * Enable hardware acceleration in Plex Web UI settings.
3. **Update Documentation:**
   * Update `ARCHITECTURE.md` with new CPU, RAM, and storage architecture.

