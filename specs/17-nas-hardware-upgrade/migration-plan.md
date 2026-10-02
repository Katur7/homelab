# M17 NAS Hardware & OS Migration Plan

## 1. Architectural Decisions

| Decision Area | Selected Strategy | Rationale |
| :--- | :--- | :--- |
| **Migration Approach** | **2-Phase Migration (Swap first, M.2 NVMe fresh OS)** | Isolates hardware validation from OS configuration. The existing Plextor SSD serves as a 100% working fallback during the transition. |
| **Base Operating System** | **Debian 12 (Bookworm) Minimal / Server** | Zero hypervisor tax, ~150MB idle RAM, direct access to Intel QuickSync GPU (`/dev/dri`), maximum stability for Docker GitOps. |
| **Host Identity & Fleet Parity** | **`grimur` (UID 1000, GID 1000)** | Full parity with Raspberry Pi (`ssh grimur@...`, `/home/grimur/homelab`). Replaces OMV's legacy `PGID=100` with standard Linux User Private Groups (`PGID=1000`). Supplementary group `users` (GID 100) retained for compatibility. |
| **Host Hardening** | **Key-Only SSH & Unattended Upgrades** | Parity with Pi Milestone 08.3: `PasswordAuthentication no`, `PermitRootLogin no`, `unattended-upgrades` active, journald capped at 1GB. |
| **Storage Architecture** | **MergerFS + SnapRAID** | Pools data drives into `/mnt/storage` for unified capacity and atomic hardlinks for Starr apps, while preserving disk-level SnapRAID parity protection. |
| **Storage Permissions** | **SetGID (`chmod 2775`) on `/mnt/storage`** | Owned by `grimur:grimur` with `umask=002` in MergerFS. New files/subfolders automatically inherit group write access across Docker (PUID/PGID 1000), SSH, and Samba. |
| **Network File Sharing** | **Samba (`smb.conf`)** | Authenticated user `grimur` for full read/write access. Read-only guest access for media streaming to smart TVs / media players. |
| **Networking** | **`systemd-networkd`** | Native, lightweight static IP configuration (`192.168.86.17/24`) with hostname `pippinn` retained for Tailscale, DNS, and Uptime Kuma continuity. |
| **SnapRAID Automation** | **Systemd Service & Timer (`scripts/`)** | Replaces OMV GUI plugin. Nightly sync with safety delete-threshold check and notification hook, plus weekly scrub. |
| **GPU Drivers & Acceleration** | **Pre-installed Intel VA-API non-free** | `intel-microcode`, `intel-media-va-driver-non-free`, and `vainfo` configured in Phase 2; `grimur` in `render` and `video` groups. |
| **Docker Management UI** | **Komodo** | GitOps-native, modern mobile-friendly web UI for restarting/monitoring containers, and multi-node support (manages both NAS and Raspberry Pi). |
| **Drive Health & Alerts** | **Beszel S.M.A.R.T. (Native)** | Built into existing Beszel fleet (`monitoring.internal.pippinn.me`). Tracks drive health, temperatures, wear, and routes failure alerts through your existing Home Assistant alert pipeline without running a heavy separate Scrutiny/InfluxDB stack. |
| **Secrets & Env Architecture** | **`.env` (Tracked) + `.secret.env` (Ignored)** | Retires the confusing `vars.env` pattern. `.env` is tracked in Git for non-sensitive configuration and native Docker Compose template interpolation (`${TAG}`, `${PORT}`). Actual credentials are isolated to gitignored `*.secret.env`. |

---

## 2. Storage Architecture: MergerFS, SnapRAID & Permissions

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

1. Install MergerFS and FUSE utilities:
   ```bash
   sudo apt update && sudo apt install -y mergerfs fuse3
   ```

2. Enable `user_allow_other` in `/etc/fuse.conf`:
   ```bash
   sudo sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf
   ```

3. Add underlying disks and unified pool to `/etc/fstab`:
   ```text
   # Underlying physical drives (mount by UUID)
   UUID=<UUID-DISK1>   /srv/disk1    ext4   defaults,noatime   0 2
   UUID=<UUID-DISK2>   /srv/disk2    ext4   defaults,noatime   0 2
   UUID=<UUID-DISK3>   /srv/disk3    ext4   defaults,noatime   0 2
   UUID=<UUID-PARITY>  /srv/parity1  ext4   defaults,noatime   0 2

   # MergerFS Unified Storage Pool (waits for physical disks to prevent race conditions)
   /srv/disk*          /mnt/storage  fuse.mergerfs  defaults,nonempty,allow_other,use_ino,cache.files=partial,category.create=mfs,minfreespace=50G,fsname=mergerfs,umask=002,x-systemd.requires-mounts-for=/srv/disk1,x-systemd.requires-mounts-for=/srv/disk2,x-systemd.requires-mounts-for=/srv/disk3  0 0
   ```

   > **Policy `category.create=mfs` (Most Free Space):** Writes new files to whichever physical drive currently has the most free space.
   > **`umask=002`:** Ensures files created by containers or users are group-writable by default.

### 2.3 Directory Structure & SetGID Permissions

Set up the unified directory structure under `/mnt/storage/` with SetGID permissions:
```bash
sudo mkdir -p /mnt/storage/{media/{movies,tv,books,audiobooks},downloads/{complete,incomplete},photos,backup}
sudo chown -R grimur:grimur /mnt/storage
sudo chmod -R 2775 /mnt/storage
```

> [!TIP]
> **SetGID (`2775`):** Ensures all new files and directories inherit group `grimur` (GID 1000) regardless of which process creates them.
> **Starr Mount Strategy:** To preserve existing Radarr and Sonarr databases without database path migrations, services will initially maintain separate mounts (`/mnt/storage/media/movies:/movies`, `/mnt/storage/downloads/complete/movies:/downloads/movies`). Consolidating to a single `/data` mount for atomic zero-copy hardlinks is deferred to a dedicated follow-up milestone.

### 2.4 Network File Sharing (Samba)

Install Samba:
```bash
sudo apt install -y samba
```

Add shares to `/etc/samba/smb.conf`:
```ini
[global]
   workgroup = WORKGROUP
   server string = pippinn NAS
   security = user
   map to guest = Bad User
   load printers = no
   printing = bsd
   printcap name = /dev/null
   disable spoolss = yes

   # macOS Performance & Metadata Optimizations (vfs_fruit)
   vfs objects = catia fruit streams_xattr
   fruit:metadata = stream
   fruit:model = Macmini
   fruit:veto_appledouble = no
   fruit:posix_rename = yes
   fruit:zero_file_id = yes
   fruit:wipe_intentionally_left_blank_rfork = yes
   fruit:delete_empty_adfiles = yes

[media]
   path = /mnt/storage/media
   browseable = yes
   read only = yes
   guest ok = yes
   write list = grimur
   create mask = 0664
   directory mask = 0775
   force group = grimur

[downloads]
   path = /mnt/storage/downloads
   browseable = yes
   read only = no
   valid users = grimur
   create mask = 0664
   directory mask = 0775
   force group = grimur

[photos]
   path = /mnt/storage/photos
   browseable = yes
   read only = no
   valid users = grimur
   create mask = 0664
   directory mask = 0775
   force group = grimur

[backup]
   path = /mnt/storage/backup
   browseable = yes
   read only = no
   valid users = grimur
   create mask = 0664
   directory mask = 0775
   force group = grimur
```

Set Samba password for `grimur`:
```bash
sudo smbpasswd -a grimur
sudo smbpasswd -e grimur
sudo systemctl restart smbd
```

### 2.5 SnapRAID Configuration & Automated Timers

1. Configure `/etc/snapraid.conf`:
   ```text
   parity /srv/parity1/snapraid.parity
   content /var/snapraid.content
   content /srv/disk1/.snapraid.content
   content /srv/disk2/.snapraid.content
   content /srv/disk3/.snapraid.content

   data d1 /srv/disk1/
   data d2 /srv/disk2/
   data d3 /srv/disk3/

   exclude *.unrecoverable
   exclude /tmp/
   exclude /lost+found/
   exclude *.!sync
   exclude .DS_Store
   exclude Thumbs.db
   ```

2. Automation via `scripts/snapraid-sync.sh`:
   * Checks `snapraid diff` before running sync.
   * Enforces a deletion threshold (e.g. aborts if >50 files were deleted unless overridden).
   * Runs `snapraid sync`.
   * Sends an alert notification if errors occur.
   * Managed via `snapraid-sync.service` and `snapraid-sync.timer` (running daily at 04:00).
   * Weekly scrub managed via `snapraid-scrub.timer` (running Sundays at 05:00 with `snapraid scrub -p 5`).

---

## 3. Management & Monitoring Services (Komodo & Beszel)

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

### 3.2 Beszel Agent: Enable Native S.M.A.R.T. Monitoring

Instead of running a separate Scrutiny stack with InfluxDB (~300MB RAM), enhance the existing [services/beszel-agent/compose.yaml](file:///Users/grimur/personal-code/homelab/services/beszel-agent/compose.yaml) to use the `:alpine` image (bundles `smartmontools`) with raw I/O disk capabilities:

```yaml
name: beszel-agent

services:
  beszel-agent:
    image: henrygd/beszel-agent:alpine
    container_name: beszel-agent
    restart: unless-stopped
    network_mode: host
    cap_add:
      - SYS_RAWIO    # Access SATA S.M.A.R.T.
      - SYS_ADMIN    # Access NVMe S.M.A.R.T.
    devices:
      - /dev/sda:/dev/sda
      - /dev/sdb:/dev/sdb
      - /dev/sdc:/dev/sdc
      - /dev/sdd:/dev/sdd
      - /dev/nvme0n1:/dev/nvme0n1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./beszel_agent_data:/var/lib/beszel-agent
    environment:
      LISTEN: 45876
      KEY: ${BESZEL_AGENT_KEY_NAS}
      TOKEN: ${BESZEL_AGENT_TOKEN_NAS}
      HUB_URL: http://192.168.86.26:8090
    deploy:
      resources:
        limits:
          cpus: "0.1"
          memory: 48M
```

> [!TIP]
> **Unified Alerting:** S.M.A.R.T. health status, drive temperatures, and failure alerts automatically flow through your existing Beszel Hub ➔ Home Assistant alert integration established in [Spec 11](file:///Users/grimur/personal-code/homelab/specs/11-monitoring/summary.md).

---

## 4. Configuration & Secrets Architecture (`.env` & `.secret.env`)

### 4.1 Problem with the Legacy `vars.env` Pattern
Docker Compose natively uses `.env` in the project directory for `${VARIABLE}` template substitution (e.g. `${IMMICH_VERSION}`, `${PORT}`). In the legacy setup:
* `.env` was gitignored and used exclusively for secrets.
* `vars.env` held non-sensitive config, but Docker Compose could not read it for template interpolation without manual `--env-file` flags.
* This caused awkward friction (e.g. `IMMICH_VERSION` had to be duplicated into untracked `.env` files).

### 4.2 The Normalized Model
We retire `vars.env` across the homelab and adopt the Docker-native standard:

| File | Git Tracking | Purpose | Examples |
| :--- | :--- | :--- | :--- |
| **`global.env`** | **Tracked** | Host-wide system identity and networking | `PUID=1000`, `PGID=1000`, `TZ=Europe/Stockholm`, `DOMAIN` |
| **`.env`** | **Tracked** | Service configuration & Compose interpolation variables | `IMMICH_VERSION=v1.120.0`, port numbers, non-secret URLs |
| **`.secret.env`** | **Gitignored** | Sensitive credentials, tokens, and passwords | `DB_PASSWORD`, API tokens, private auth keys |

### 4.3 Standard Compose Pattern
In each service's `compose.yaml`:
```yaml
services:
  app:
    image: ghcr.io/example/app:${APP_VERSION:-latest} # interpolated from .env
    env_file:
      - ../../global.env
      - .env
      - .secret.env # included only if service requires secrets
```

### 4.4 `.gitignore` Rules
Update `.gitignore` to allow tracked `.env` while strictly ignoring secrets:
```gitignore
# Secrets
*.secret.env
.secret.env
```

---

## 5. Step-by-Step Execution Plan

### Phase 1: Physical Hardware Swap & Validation (Existing SSD)

1. **Pre-flight on old hardware:**
   * Run Borg backup / ensure offsite Pi backup is fresh (`sudo /home/grimur/homelab/infrastructure/backup/backup-to-pi.sh`).
   * **Extract & securely backup host credentials to your password manager or Mac:**
     - `/root/.borg-passphrase` (critical: required to decrypt backups on fresh OS)
     - `/root/.ssh/id_ed25519_backup_pi` (critical: required to SSH into `pi-backup`)
     - Any active secret `.env` files not yet backed up
   * Note Home Assistant USB coordinator details: `ls -l /dev/serial/by-id/` or `/dev/ttyUSB0`.
   * Install Intel microcode in advance: `sudo apt install -y intel-microcode`
   * Clean shutdown: `sudo poweroff`
2. **Assembly & Physical Setup:**
   * Install generic N150 motherboard, RAM, and CPU cooler into Fractal Node 304.
   * Connect 24-pin ATX + 4-pin CPU power.
   * Connect Plextor SATA SSD (Port 1) and 4x HDDs (Ports 2–5).
   * Reconnect Home Assistant USB coordinator dongle to a USB port.
   * Connect LAN cable to Port 1 (Intel i226-V).
   * Update router DHCP reservation for `pippinn` (`192.168.86.17`) with the new NIC's MAC address once first booted.
3. **First Boot & BIOS Check:**
   * Attach monitor + keyboard.
   * Verify 32GB RAM detected in BIOS.
   * Confirm UEFI boot mode (existing Plextor installation is verified UEFI).
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
   * Set hostname to `pippinn`.
   * Create primary user `grimur` (UID 1000, GID 1000).

2. **Network Configuration (`systemd-networkd`):**
   * Identify primary 2.5GbE interface (e.g. `enp1s0` via `ip link`).
   * Create `/etc/systemd/network/10-lan.network`:
     ```ini
     [Match]
     Name=enp1s0

     [Network]
     Address=192.168.86.17/24
     Gateway=192.168.86.1
     DNS=192.168.86.26
     DNS=192.168.86.1
     ```
   * Enable and start `systemd-networkd`:
     ```bash
     sudo systemctl enable --now systemd-networkd
     sudo systemctl enable --now systemd-resolved
     ```

3. **User Groups, Host Hardening & Swap:**
   * Add user `grimur` to required groups:
     ```bash
     sudo usermod -aG sudo,docker,render,video,users grimur
     ```
   * Deploy SSH public keys to `/home/grimur/.ssh/authorized_keys`.
   * Apply SSH hardening in `/etc/ssh/sshd_config.d/hardening.conf`:
     ```text
     PasswordAuthentication no
     PermitRootLogin no
     ```
   * Restart SSH: `sudo systemctl restart ssh`
   * Install and configure `unattended-upgrades`:
     ```bash
     sudo apt update && sudo apt install -y unattended-upgrades
     sudo dpkg-reconfigure -plow unattended-upgrades
     ```
   * Cap systemd journal in `/etc/systemd/journald.conf`:
     ```ini
     [Journal]
     SystemMaxUse=1G
     ```
     `sudo systemctl restart systemd-journald`
   * Configure 8GB NVMe swapfile with conservative swappiness (`vm.swappiness=10`):
     ```bash
     sudo fallocate -l 8G /swapfile
     sudo chmod 600 /swapfile
     sudo mkswap /swapfile
     sudo swapon /swapfile
     echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
     echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf
     sudo sysctl --system
     ```

4. **Package & Driver Installation:**
   * Ensure `non-free-firmware` and `non-free` are enabled in `/etc/apt/sources.list`.
   * Install packages:
     ```bash
     sudo apt update && sudo apt install -y \
       curl git mergerfs snapraid samba smartmontools \
       intel-microcode intel-media-va-driver-non-free vainfo fuse3
     ```
   * Verify QuickSync VA-API drivers:
     ```bash
     vainfo
     ```
   * Install Docker Engine & Compose plugin:
     ```bash
     curl -fsSL https://get.docker.com | sh
     ```

5. **Storage, Mounts & Permissions:**
   * Create mount points: `/srv/disk1`, `/srv/disk2`, `/srv/disk3`, `/srv/parity1`, `/mnt/storage`.
   * Populate `/etc/fstab` with drive UUIDs and MergerFS pool (Section 2.2).
   * Configure `/etc/fuse.conf` (`user_allow_other`).
   * Mount all filesystems: `sudo mount -a`.
   * Apply SetGID directory permissions:
     ```bash
     sudo chown -R grimur:grimur /mnt/storage
     sudo chmod -R 2775 /mnt/storage
     ```
   * Normalize existing HDD file ownership if necessary:
     ```bash
     sudo chown -R grimur:grimur /srv/disk1 /srv/disk2 /srv/disk3
     ```
   * Configure Samba (`/etc/samba/smb.conf`) and set `grimur` SMB password.
   * Recreate `/etc/snapraid.conf` pointing to `/srv/disk*` and `/srv/parity1`.

6. **GitOps Deployment & Config Normalization:**
   * Clone repo to `/home/grimur/homelab`.
   * Update `.gitignore` to allow tracked `.env` and ignore `*.secret.env`.
   * **Execute `.env` & `.secret.env` Migration:**
     - Rename all `vars.env` files to `.env` (`git mv <dir>/vars.env <dir>/.env`).
     - Restore secret `.env` files from Borg backup as `.secret.env`.
     - Update `compose.yaml` files referencing `vars.env` to `.env` (and add `.secret.env` where secrets exist).
   * Update [global.env](file:///Users/grimur/personal-code/homelab/global.env) to normalize `PGID=1000`:
     ```env
     PUID=1000
     PGID=1000
     ```
   * Update [services/vikunja/compose.yaml](file:///Users/grimur/personal-code/homelab/services/vikunja/compose.yaml) to `user: 1000:1000`.
   * Update [services/beszel-agent/compose.yaml](file:///Users/grimur/personal-code/homelab/services/beszel-agent/compose.yaml) to `:alpine` with `cap_add` and `/dev/*` devices for S.M.A.R.T. monitoring (Section 3.2).
   * **Update Storage Mount Paths in `services/*/compose.yaml`:**
     - Map `/srv/dev-disk-by-uuid-.../...` to `/mnt/storage/...`.
     - *Important:* Keep right-hand container-side paths identical (`/mnt/storage/media/movies:/movies`, `/mnt/storage/photos:/data`, etc.) to preserve Radarr, Sonarr, Plex, and Immich databases without triggering library rescans or lost watch states.
   * **Restore Traefik Certificates:**
     - Restore `acme.json` and enforce strict permissions:
       ```bash
       chmod 600 /home/grimur/homelab/infrastructure/gateway/config/acme.json
       ```
   * **Verify Home Assistant USB Coordinator:**
     - Confirm the USB coordinator is present: `ls -l /dev/ttyUSB*` (or `/dev/serial/by-id/*`).
   * Set up Docker maintenance:
     ```bash
     sudo /home/grimur/homelab/scripts/setup-docker-maintenance.sh
     ```
   * Start homelab stack:
     ```bash
     ./scripts/homelab-up.sh
     ```

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
3. **Deploy SnapRAID Automation Timers:**
   * Link and enable `scripts/snapraid-sync.timer` and `scripts/snapraid-scrub.timer`.
4. **Deploy Automated Borg Backup Systemd Timer:**
   * Create and enable `borg-backup.service` and `borg-backup.timer` to schedule `infrastructure/backup/backup-to-pi.sh` nightly at 02:00, replacing the OMV Borg plugin.
5. **Update Documentation:**
   * Update `ARCHITECTURE.md` with new CPU, RAM, and storage architecture.
