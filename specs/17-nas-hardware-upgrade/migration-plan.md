# M17 NAS Hardware & OS Migration Plan

## 1. Architectural Decisions

| Decision Area | Selected Strategy | Rationale |
| :--- | :--- | :--- |
| **Migration Approach** | **2-Phase Migration (Swap first, M.2 NVMe fresh OS)** | Isolates hardware validation from OS configuration. The existing Plextor SSD serves as a 100% working fallback during the transition. |
| **Base Operating System** | **Debian 12 (Bookworm) Minimal / Server** | Zero hypervisor tax, ~150MB idle RAM, direct access to Intel QuickSync GPU (`/dev/dri`), maximum stability for Docker GitOps. |
| **Host Identity & Fleet Parity** | **`grimur` (UID 1000, GID 1000)** | Full parity with Raspberry Pi (`ssh grimur@...`, `/home/grimur/homelab`). Replaces OMV's legacy `PGID=100` with standard Linux User Private Groups (`PGID=1000`). Supplementary group `users` (GID 100) retained for compatibility. |
| **Host Hardening** | **Key-Only SSH, Fail2Ban & Unattended Upgrades** | Parity with Pi Milestone 08.3 & OMV 07.4: `PasswordAuthentication no`, `PermitRootLogin no`, Fail2Ban SSH jail with ban-only email alerts, `unattended-upgrades` active, journald capped at 1GB. |
| **Storage Architecture** | **MergerFS + SnapRAID** | Pools data drives into `/mnt/storage` for unified capacity and atomic hardlinks for Starr apps, while preserving disk-level SnapRAID parity protection. |
| **Storage Permissions** | **SetGID (`chmod 2775`) on `/mnt/storage`** | Owned by `grimur:grimur` with `umask=002` in MergerFS. New files/subfolders automatically inherit group write access across Docker (PUID/PGID 1000), SSH, and Samba. |
| **Network File Sharing** | **Samba (`smb.conf`)** | Authenticated user `grimur` for full read/write access. Read-only guest access for media streaming to smart TVs / media players. |
| **Networking** | **`systemd-networkd`** | Native, lightweight static IP configuration (`192.168.86.17/24`) with hostname `pippinn` retained for Tailscale, DNS, and Uptime Kuma continuity. |
| **SnapRAID Automation** | **Systemd Service & Timer (`scripts/`)** | Replaces OMV GUI plugin. Nightly sync with safety delete-threshold check and notification hook, plus weekly scrub. |
| **GPU Drivers & Acceleration** | **Pre-installed Intel VA-API non-free** | `intel-microcode`, `intel-media-va-driver-non-free`, and `vainfo` configured in Phase 2; `grimur` in `render` and `video` groups. |
| **Docker Management UI** | **Dozzle** | Lightweight, stateless web UI for real-time container log streaming, memory/CPU monitoring, and one-click container lifecycle management (start/stop/restart) exposed at `logs.internal.pippinn.me`. |
| **Drive Health & Alerts** | **Beszel S.M.A.R.T. (Native)** | Built into existing Beszel fleet (`monitoring.internal.pippinn.me`). Tracks drive health, temperatures, wear, and failure alerts with email notifications without running a heavy separate Scrutiny/InfluxDB stack. |
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

1. Configure `/etc/snapraid.conf` (preserving array layout and exclude lists from OMV):
   ```text
   # SnapRAID Configuration for pippinn NAS
   # Parity disk (UUID 9e6b2fd0-7b7e-4045-bd96-c2e925089d1a)
   parity /srv/parity1/snapraid.parity

   # Content list files (1 on root SSD + 1 on each data disk)
   content /var/snapraid.content
   content /srv/disk1/.snapraid.content
   content /srv/disk2/.snapraid.content
   content /srv/disk3/.snapraid.content

   # Data disks
   data d1 /srv/disk1/
   data d2 /srv/disk2/
   data d3 /srv/disk3/

   # Excludes (retained from OMV array configuration)
   exclude *.unrecoverable
   exclude lost+found/
   exclude aquota.user
   exclude aquota.group
   exclude /tmp/
   exclude .content
   exclude *.bak
   exclude /snapraid.conf*
   exclude /photos/thumbs/
   exclude /code/
   exclude /photos/encoded-video/
   exclude /backup/borg/
   exclude /backup/borg2/
   exclude /backup/omv-backup/
   exclude /syncthing/.stversions/
   exclude *.!sync
   exclude .DS_Store
   exclude Thumbs.db
   ```

2. Automation via `scripts/snapraid-sync.sh` and `scripts/snapraid-scrub.sh`:
   * **Mountpoint Safety Verification:** Checks that all underlying disk paths (`/srv/disk1`, `/srv/disk2`, `/srv/disk3`, `/srv/parity1`) are active mountpoints (`mountpoint -q`) before running any SnapRAID commands. Prevents disastrous parity corruption if an unmounted disk appears empty.
   * **Pre-Sync Diff & Deletion Threshold:** Runs `snapraid diff` and parses the count of removed files. If deletions exceed `DEL_THRESHOLD` (default: 50 files), the script aborts with an alert to protect against accidental mass deletions.
   * **Threshold Override:** Can be bypassed via `--force` CLI argument or by creating the flag file `touch /tmp/snapraid-sync.force`.
   * **Error-Only Email Alerts:** Sends an immediate alert email (using `msmtp` / `mail` configured in `/etc/msmtprc`) with the error output, diff summary, and exit code if a sync or scrub fails, or if the deletion threshold is exceeded. Successful daily runs remain silent.
   * **Uptime Kuma Heartbeat Push Monitors:**
     - `snapraid-sync`: Expected daily (interval 25 hours). Dead-man's switch triggered if sync fails to run or complete.
     - `snapraid-scrub`: Expected weekly (interval 8 days). Dead-man's switch triggered if weekly Sunday scrub fails to run or complete.
   * **Weekly Scrub (`scripts/snapraid-scrub.sh`):** Runs `snapraid scrub -p 5 -o 10` (scrubs 5% of array older than 10 days) with mount safety checks, error emails, and scrub heartbeat ping.
   * **Systemd Timers:** Managed via `snapraid-sync.timer` (daily at 04:00) and `snapraid-scrub.timer` (Sundays at 05:00). Installed via `scripts/setup/snapraid/setup.sh`.

---

## 3. Management & Monitoring Services (Dozzle & Beszel)

### 3.1 Dozzle (Real-time Container Logs & Lifecycle Management)

Dozzle provides a lightweight, real-time log viewer and container dashboard across all Docker services running on the host.

* **Configuration:** Defined in `services/dozzle/compose.yaml` (uses `amir20/dozzle:latest`).
* **Networking & Ingress:** Connected to `traefik_internal`, exposed securely at `https://logs.internal.pippinn.me`.
* **Zero Database Overhead:** Completely stateless; interacts directly with Docker via the UNIX socket (`/var/run/docker.sock`).
* **Container Actions:** Configured with `DOZZLE_ENABLE_ACTIONS: "true"` to allow one-click container start, stop, and restart directly from the web interface without touching disk files.
* **Authentication & SSO:** Protected by Authelia via Traefik's `authelia-auth@file` forward-auth middleware and `DOZZLE_AUTH_PROVIDER: forward-proxy`. Uses `./data:/data` to persist user settings and preferences.
* **Resource Footprint:** Extremely light (~20MB RAM, minimal CPU).

```yaml
name: dozzle

services:
  dozzle:
    image: amir20/dozzle:latest
    container_name: dozzle
    restart: unless-stopped
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./data:/data
    environment:
      DOZZLE_ENABLE_ACTIONS: "true"
      DOZZLE_AUTH_PROVIDER: forward-proxy
    networks:
      - traefik_internal
    labels:
      - "wud.autoupdate=true"
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_internal"
      - "traefik.http.routers.dozzle-internal.entrypoints=websecure"
      - "traefik.http.routers.dozzle-internal.rule=Host(`logs.internal.pippinn.me`)"
      - "traefik.http.routers.dozzle-internal.middlewares=authelia-auth@file"
      - "traefik.http.services.dozzle-internal.loadbalancer.server.port=8080"
    deploy:
      resources:
        limits:
          cpus: "0.25"
          memory: 64M

networks:
  traefik_internal:
    external: true
```

### 3.2 Beszel: Native S.M.A.R.T. Monitoring & Email Alerts

Instead of running a heavy separate Scrutiny + InfluxDB stack (~300MB RAM), Beszel agent on the NAS is upgraded to `henrygd/beszel-agent:alpine` (which bundles `smartmontools`) with raw drive passthrough to deliver lightweight (~15MB RAM) drive health, temperature, and wear monitoring.

#### Beszel Agent Architecture (`services/beszel-agent/compose.yaml`)
* **Host Access:** `network_mode: host` for accurate NIC and network metrics.
* **Capabilities:** `SYS_RAWIO` (SATA S.M.A.R.T.) and `SYS_ADMIN` (NVMe S.M.A.R.T.).
* **Device Nodes:** Passthrough for `/dev/sda`, `/dev/sdb`, `/dev/sdc`, `/dev/sdd`, `/dev/sde`, and `/dev/nvme0n1`.
* **Udev:** Mounts `/run/udev:ro` for device identification and disk serials.

#### Alerting Pipeline
Beszel Hub (running on the Raspberry Pi at `192.168.86.26:8090`) routes alerts directly to email via its built-in notification settings (**Settings ➔ Notifications**):

1. **Email Configuration (SMTP):**
   Configured in Beszel Hub UI using your SMTP provider (or Shoutrrr SMTP URL):
   ```text
   smtp://grimurk%40gmail.com:<gmail-app-password>@smtp.gmail.com:587/?fromaddress=grimurk@gmail.com&toaddresses=grimurk@gmail.com
   ```

2. **Configured Alert Rules in Beszel Hub:**
   * **Drive S.M.A.R.T. Status:** Immediate alert if any drive reports degraded health or pre-fail attributes.
   * **HDD Temperature:** Alert if any mechanical drive exceeds 45°C.
   * **NVMe Temperature:** Alert if the NVMe system drive exceeds 70°C.
   * **Disk Space Usage:** Alert if any filesystem exceeds 90% utilization.
   * **Host Availability:** Alert if NAS or Pi agent disconnects for >5 minutes.

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
     sudo usermod -aG sudo,render,video,users grimur
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
   * Install base packages and GPU acceleration libraries:
     ```bash
     sudo apt update && sudo apt install -y \
       curl git mergerfs snapraid samba smartmontools pciutils \
       intel-microcode intel-media-va-driver-non-free vainfo fuse3
     ```
   * **Intel N150 GPU Support (Kernel 6.12 via Backports):**
     The Intel N150 ("Twin Lake", PCI ID `8086:46d4`) was released after Debian 12's Linux 6.1 kernel. Enable `bookworm-backports` to install the 6.12+ kernel and updated non-free firmware:
     ```bash
     echo "deb http://deb.debian.org/debian bookworm-backports main contrib non-free non-free-firmware" | sudo tee /etc/apt/sources.list.d/backports.list
     sudo apt update
     sudo apt install -t bookworm-backports -y linux-image-amd64 firmware-misc-nonfree
     sudo reboot
     ```
   * Verify QuickSync VA-API drivers after reboot:
     ```bash
     vainfo --display drm --device /dev/dri/renderD128
     ```
   * Install Docker Engine & Compose plugin:
     ```bash
     curl -fsSL https://get.docker.com | sh
     sudo usermod -aG docker grimur
     ```

5. **Storage, Mounts & Permissions:**
   * Create mount points:
     ```bash
     sudo mkdir -p /srv/{disk1,disk2,disk3,parity1} /mnt/storage
     ```
   * Populate `/etc/fstab` with drive UUIDs and MergerFS pool:
     ```text
     # Underlying physical drives (mount by UUID)
     UUID=220b73c9-2682-4822-b871-cb499733b15b   /srv/disk1    ext4   defaults,noatime   0 2
     UUID=0ddafbf7-f06d-424d-8e9c-95d97fbd4484   /srv/disk2    ext4   defaults,noatime   0 2
     UUID=f1209e02-5b26-491f-ac40-f951e9ddfbb0   /srv/disk3    ext4   defaults,noatime   0 2
     UUID=9e6b2fd0-7b7e-4045-bd96-c2e925089d1a   /srv/parity1  ext4   defaults,noatime   0 2

     # MergerFS Unified Storage Pool
     /srv/disk*          /mnt/storage  fuse.mergerfs  defaults,nonempty,allow_other,use_ino,cache.files=partial,category.create=mfs,minfreespace=50G,fsname=mergerfs,umask=002,x-systemd.requires-mounts-for=/srv/disk1,x-systemd.requires-mounts-for=/srv/disk2,x-systemd.requires-mounts-for=/srv/disk3  0 0
     ```
   * Configure `/etc/fuse.conf`:
     ```bash
     sudo sed -i 's/#user_allow_other/user_allow_other/' /etc/fuse.conf
     ```
   * Mount all filesystems and verify:
     ```bash
     sudo mount -a
     df -h /mnt/storage /srv/disk* /srv/parity1
     ```
   * Apply SetGID directory permissions:
     ```bash
     sudo chown -R grimur:grimur /mnt/storage
     sudo chmod -R 2775 /mnt/storage
     ```
   * Normalize existing HDD file ownership if necessary:
     ```bash
     sudo chown -R grimur:grimur /srv/disk1 /srv/disk2 /srv/disk3
     ```
   * Configure Samba (`/etc/samba/smb.conf`) and set `grimur` SMB password:
     ```bash
     sudo smbpasswd -a grimur
     sudo smbpasswd -e grimur
     sudo systemctl restart smbd
     ```
   * Deploy `/etc/snapraid.conf` (Section 2.5).

6. **GitOps Deployment & Service Bring-Up:**
   * Clone repo to `/home/grimur/homelab`.
   * **Overlay Runtime State, Databases & Secrets from Old SSD:**
     Keep the existing `vars.env` + `.env` pattern intact during bring-up to avoid breaking container startups. Copy runtime state from the attached Plextor SSD (`/mnt/old-omv`):
     ```bash
     sudo rsync -av --keep-dirlinks \
       --include='*/' \
       --include='.env' \
       --include='acme.json' \
       --include='*.db' \
       --include='*.sqlite3' \
       /mnt/old-omv/home/grimur/homelab/ /home/grimur/homelab/
     sudo chown -R grimur:grimur /home/grimur/homelab
     chmod 600 /home/grimur/homelab/infrastructure/gateway/config/acme.json 2>/dev/null
     chmod +x /home/grimur/homelab/scripts/*.sh
     ```
     > [!NOTE]
     > **Deferred `.env` Normalization:** Retiring `vars.env` in favor of `.env` / `.secret.env` is deferred to Phase 3 (Post-Migration) so the stack can be brought up and validated with zero configuration churn.
   * Update [global.env](file:///Users/grimur/personal-code/homelab/global.env) to normalize `PGID=1000`:
     ```env
     PUID=1000
     PGID=1000
     ```
   * Update [services/vikunja/compose.yaml](file:///Users/grimur/personal-code/homelab/services/vikunja/compose.yaml) to `user: 1000:1000`.
   * Update [services/beszel-agent/compose.yaml](file:///Users/grimur/personal-code/homelab/services/beszel-agent/compose.yaml) to `:alpine` with `cap_add` and `/dev/*` devices for S.M.A.R.T. monitoring (Section 3.2).
   * **Update Storage Mount Paths in `services/*/compose.yaml`:**
     - Map `/srv/dev-disk-by-uuid-.../...` to `/mnt/storage/...`.
     - *Important:* Keep right-hand container-side paths identical (`/mnt/storage/movies:/movies`, `/mnt/storage/photos:/data`, etc.) to preserve Radarr, Sonarr, Plex, and Immich databases without triggering library rescans or lost watch states.
   * **Verify Home Assistant USB Coordinator:**
     - Confirm the USB coordinator is present: `ls -l /dev/ttyUSB*` (or `/dev/serial/by-id/*`).
   * Set up Docker maintenance:
     ```bash
     sudo /home/grimur/homelab/scripts/setup/docker/setup.sh
     ```
   * Bring up core infrastructure stacks first (creates `traefik_internal` and core networks):
     ```bash
     docker compose -f infrastructure/gateway/compose.yaml up -d
     docker compose -f infrastructure/dns/compose.yaml up -d
     docker compose -f infrastructure/tailscale/compose.yaml up -d
     ```
   * Bring up remaining service stacks:
     ```bash
     for dir in services/*/; do
       [ -f "${dir}compose.yaml" ] && docker compose -f "${dir}compose.yaml" up -d
     done
     ```

7. **Configure Host Email Relay (`msmtp`):**
   * Install lightweight mail relay packages:
     ```bash
     sudo apt update && sudo apt install -y msmtp msmtp-mta bsd-mailx
     ```
   * Configure `/etc/msmtprc`:
     ```ini
     # /etc/msmtprc — System-wide SMTP relay configuration
     defaults
     auth           on
     tls            on
     tls_trust_file /etc/ssl/certs/ca-certificates.crt
     syslog         LOG_MAIL

     account        default
     host           smtp.gmail.com
     port           587
     from           grimurk@gmail.com
     user           grimurk@gmail.com
     password       <gmail-app-password>
     ```
     > [!NOTE]
     > For Gmail, `<gmail-app-password>` must be a 16-character Google App Password (generated via Google Account → Security → 2-Step Verification → App passwords).
   * Secure configuration permissions & grant non-root access:
     ```bash
     # Restrict to root and msmtp group so unprivileged users/services can send mail without sudo
     sudo chown root:msmtp /etc/msmtprc
     sudo chmod 640 /etc/msmtprc
     sudo usermod -aG msmtp grimur
     newgrp msmtp  # Activate group membership in current session without relogging
     ```
   * Verify system MTA symlink:
     ```bash
     ls -l /usr/sbin/sendmail
     # Should point to /usr/bin/msmtp
     ```
   * Test email delivery (run as regular user `grimur` without `sudo`):
     ```bash
     # Test via verbose msmtp command (shows SMTP handshake / auth)
     printf "Subject: Test from msmtp\n\nThis is a test email." | msmtp -v grimurk@gmail.com

     # Test via mail wrapper
     echo "Test mail from pippinn NAS" | mail -s "Test Email" grimurk@gmail.com

     # Inspect delivery log in systemd journal
     journalctl -t msmtp -n 10
     ```

8. **Install & Configure Fail2Ban for SSH (with Ban-Only Email Alerts):**
   * Install Fail2Ban and WHOIS utility:
     ```bash
     sudo apt update && sudo apt install -y fail2ban whois
     ```
   * Protects SSH from brute-force connection floods while emailing detailed ban reports with WHOIS information (suppressing start/stop reboot noise, per Milestone 07.4).
   * Create ban-only action override in `/etc/fail2ban/action.d/sendmail-whois-lines-banonly.conf`:
     ```ini
     [INCLUDES]
     before = sendmail-whois-lines.conf

     [Definition]
     actionstart =
     actionstop =
     ```
   * Configure `/etc/fail2ban/jail.local`:
     ```ini
     [DEFAULT]
     backend = systemd
     bantime = 1h
     findtime = 10m
     maxretry = 5
     ignoreip = 127.0.0.1/8 ::1 192.168.86.0/24

     destemail = grimurk@gmail.com
     sender = grimurk@gmail.com
     mta = mail

     # Block IP at firewall and send detailed email on ban
     action = %(banaction)s[name=%(__name__)s, port="%(port)s", protocol="%(protocol)s", chain="%(chain)s"]
              sendmail-whois-lines-banonly[name=%(__name__)s, dest="%(destemail)s", chain="%(chain)s", sender="%(sender)s"]

     [sshd]
     enabled = true
     port = ssh
     ```
   * Enable and start Fail2Ban:
     ```bash
     sudo systemctl enable --now fail2ban
     sudo fail2ban-client status sshd
     ```

9. **Deploy Dozzle Dashboard (`logs.internal.pippinn.me`):**
   * Bring up the Dozzle container:
     ```bash
     docker compose -f services/dozzle/compose.yaml pull
     docker compose -f services/dozzle/compose.yaml up -d
     ```
   * Open `https://logs.internal.pippinn.me` in your browser.
   * Verify all running and stopped containers appear immediately with live logs, stats, and start/stop/restart action buttons.
   * *(Optional)* To monitor the Raspberry Pi in the same view, deploy a Dozzle agent container on the Pi.

10. **Verify Beszel Agent & Configure Email Notifications:**
   * Verify Beszel Agent container status:
     ```bash
     docker compose -f services/beszel-agent/compose.yaml logs -f
     ```
   * Open Beszel Hub at `https://monitoring.internal.pippinn.me`.
   * Confirm the `pippinn` NAS system is connected and reporting:
     - All 4 SATA HDDs (`/dev/sda`, `/dev/sdb`, `/dev/sdc`, `/dev/sdd`) and NVMe (`/dev/nvme0n1`) show active S.M.A.R.T. health status and temperatures.
     - Filesystem usage for `/` and `/mnt/storage` is tracked accurately.
   * **Configure Email Notifications in Beszel Hub:**
     - Navigate to **Settings ➔ Notifications ➔ Add Notification Provider ➔ Email (SMTP)**.
     - Configure SMTP relay (or Shoutrrr SMTP URL) with your SMTP provider to deliver alerts to `grimurk@gmail.com`.
   * **Configure Alert Rules in Beszel Hub:**
     - Drive Temperature: Alert if HDD > 45°C or NVMe > 70°C.
     - S.M.A.R.T. Health: Alert immediately on failing attribute.
     - Disk Space: Alert if usage > 90%.
     - Host Availability: Alert if offline for > 5 minutes.
   * **Test Notification:**
     - Click **Send Test** in Beszel Hub and verify test email arrives in your inbox.

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
3. **Deploy SnapRAID Validation & Automation Timers:**
   * **Step A: Pre-flight Diff Check:**
     Verify existing parity data matches the data drives without writing changes:
     ```bash
     sudo snapraid diff
     ```
     *(Confirm output reports clean status or expected differences).*
   * **Step B: Test Automated Sync Script:**
     Run the sync script manually to verify mount safety checks, diff parsing, and threshold logic:
     ```bash
     sudo /home/grimur/homelab/scripts/snapraid-sync.sh
     ```
     *(If testing with a large deletion batch, verify abort logic, or test bypass via `--force` or `touch /tmp/snapraid-sync.force`).*
   * **Step C: Create Uptime Kuma Push Monitors:**
     In Uptime Kuma UI (`https://status.internal.pippinn.me` or `http://192.168.86.26:3001`):
     1. Add Monitor:
        - **Type:** Push
        - **Name:** `snapraid-sync`
        - **Heartbeat Interval:** `25 hours` (86400s + buffer for daily 04:00 sync)
        - Copy the push URL.
     2. Add Monitor:
        - **Type:** Push
        - **Name:** `snapraid-scrub`
        - **Heartbeat Interval:** `8 days` (buffer for weekly Sunday 05:00 scrub)
        - Copy the push URL.
   * **Step D: Configure Notification Settings:**
     Copy the template and fill in the push URLs and recipient email:
     ```bash
     sudo cp /home/grimur/homelab/scripts/setup/snapraid/snapraid-notify.conf.example /etc/snapraid-notify.conf
     sudo chmod 600 /etc/snapraid-notify.conf
     sudo nano /etc/snapraid-notify.conf
     ```
     Ensure:
     - `NOTIFY_EMAIL="grimurk@gmail.com"` (receives immediate email alerts if sync/scrub fails or deletion threshold is exceeded)
     - `UPTIME_KUMA_PUSH_URL_SYNC="<push-url-from-kuma>"`
     - `UPTIME_KUMA_PUSH_URL_SCRUB="<push-url-from-kuma>"`
   * **Step E: Install & Enable Systemd Timers:**
     Deploy daily sync (04:00) and weekly scrub (Sun 05:00) timers:
     ```bash
     sudo /home/grimur/homelab/scripts/setup/snapraid/setup.sh
     ```
   * **Step F: Verify Timer Status & Heartbeat:**
     - Check timer activation:
       ```bash
       systemctl list-timers snapraid-*.timer
       ```
     - Run a test sync:
       ```bash
       sudo /home/grimur/homelab/scripts/snapraid-sync.sh
       ```
4. **Deploy Automated Borg Backup Systemd Timers:**
   * Replaces the OMV BorgBackup plugin with native systemd timers for both local NAS backups (`/mnt/storage/backup/borg2`) and offsite backup to `pi-backup`.
   * **Step A: Verify Credentials & Passphrase:**
     Ensure credentials extracted from the old system exist with restricted permissions:
     ```bash
     sudo chmod 600 /root/.borg-passphrase
     sudo chmod 600 /root/.ssh/id_ed25519_backup_pi 2>/dev/null || true
     ```
   * **Step B: Test Local Backup Script:**
     Verify local backups run cleanly against `/mnt/storage/backup/borg2`:
     ```bash
     # Test homelab configuration backup (excludes hot DBs, logs, caches)
     sudo /home/grimur/homelab/infrastructure/backup/backup-local.sh homelab

     # Test photos backup
     sudo /home/grimur/homelab/infrastructure/backup/backup-local.sh photos

     # Confirm archives exist in repository
     export BORG_PASSCOMMAND='cat /root/.borg-passphrase'
     borg list /mnt/storage/backup/borg2
     ```
   * **Step C: Configure Uptime Kuma Push Heartbeats (Optional):**
     Create push monitors in Uptime Kuma and populate local heartbeat files:
     ```bash
     echo "http://192.168.86.26:3001/api/push/<homelab-token>?status=up&msg=OK&ping=" | sudo tee /root/.uptime-kuma-push-local-homelab
     echo "http://192.168.86.26:3001/api/push/<photos-token>?status=up&msg=OK&ping=" | sudo tee /root/.uptime-kuma-push-local-photos
     echo "http://192.168.86.26:3001/api/push/<offsite-token>?status=up&msg=OK&ping=" | sudo tee /root/.uptime-kuma-push-offsite
     ```
   * **Step D: Install & Enable Systemd Timers:**
     Run the setup script to install service units and enable timers:
     ```bash
     sudo /home/grimur/homelab/scripts/setup/borg/setup.sh
     ```
     This activates:
     - `borg-backup-local-homelab.timer`: Daily at 02:00
     - `borg-backup-local-photos.timer`: Weekly Mondays at 03:00
     - `borg-backup-offsite.timer`: Weekly Sundays at 04:00
   * **Step E: Verify Timers & Logs:**
     ```bash
     systemctl list-timers borg-backup-*.timer
5. **Deploy WireGuard Uptime Monitoring Systemd Timer:**
   * Monitors the WireGuard container and `wg0` interface health, pushing heartbeats to Uptime Kuma every 5 minutes (replaces legacy `/etc/cron.d/wireguard-uptime`).
   * **Step A: Verify Push Secret:**
     Ensure the secret push URL file exists with restricted permissions:
     ```bash
     sudo chmod 600 /root/.uptime-kuma-push-wireguard
     ```
   * **Step B: Test Health Check Script:**
     Run the check script manually to verify Docker inspection, `wg show wg0`, and push notification:
     ```bash
     sudo /home/grimur/homelab/infrastructure/wireguard/scripts/uptime-push.sh
     ```
   * **Step C: Install & Enable Systemd Timer:**
     Run the setup script to validate prerequisites and enable the 5-minute timer:
     ```bash
     sudo /home/grimur/homelab/scripts/setup/wireguard/setup.sh
     ```
   * **Step D: Verify Timer & Status:**
     ```bash
     systemctl list-timers wireguard-uptime.timer
     journalctl -u wireguard-uptime.service -n 20
     ```

6. **Execute `.env` & `.secret.env` Normalization (from Section 4):**

   * Rename all `vars.env` files to `.env` (`git mv <dir>/vars.env <dir>/.env`).
   * Rename all secret `.env` files to `.secret.env` (`mv <dir>/.env <dir>/.secret.env`).
   * Update `.gitignore` to allow tracked `.env` and ignore `*.secret.env`.
   * Update `compose.yaml` files referencing `vars.env` to `.env` (and add `.secret.env` where secrets exist).
   * Verify all containers reload cleanly with `docker compose config`.
7. **Update Documentation:**
   * Update `ARCHITECTURE.md` with new CPU, RAM, and storage architecture.
