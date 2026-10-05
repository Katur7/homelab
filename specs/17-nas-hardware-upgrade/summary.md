# Milestone 17: NAS Hardware Upgrade & Clean Debian 12 Migration — Summary

## What Changed

### 1. Hardware Architecture Upgrade
- **CPU & Motherboard:** Upgraded from dual-core AMD E-350 (2C/2T, 1.6GHz, below x86-64-v2) to quad-core **Intel N150** ("Twin Lake", 4C/4T, up to 3.6GHz, AVX2 / x86-64-v3 support, Intel UHD Graphics QuickSync).
- **RAM:** Upgraded from 8GB DDR3 to **32GB DDR4** 3200MHz.
- **OS Drive:** Upgraded from 128GB Plextor SATA SSD to **1TB Kingston NV8 M.2 NVMe SSD** with standard Debian 12 Minimal (Linux 6.12 via bookworm-backports).
- **Network:** Upgraded to integrated Intel i226-V 2.5GbE controller (`192.168.86.17`).

### 2. Operating System & Storage Architecture
- **Clean Debian 12 (No OMV):** Retired OpenMediaVault and all its proprietary plugins in favor of standard Linux primitives and native systemd timers.
- **MergerFS Storage Pool (`/mnt/storage`):** Pools underlying 3x 3TB ext4 HDDs (`/srv/disk1`, `/srv/disk2`, `/srv/disk3`) with atomic cross-directory hardlinks for Starr apps and unified SMB shares.
- **SnapRAID Parity Protection:** Dedicated parity on `/srv/parity1/snapraid.parity` with automated daily sync at 04:00 (including pre-sync diff check and deletion threshold safety aborts) and weekly scrub on Sundays at 05:00.

### 3. Modular Systemd Maintenance Suites (`scripts/setup/`)
Replaced OMV GUI plugins and ad-hoc cron jobs with structured systemd automation:
- **`scripts/setup/snapraid/setup.sh`:** Deploys `snapraid-sync.timer` (04:00) and `snapraid-scrub.timer` (Sun 05:00) with failure email alerts.
- **`scripts/setup/borg/setup.sh`:** Deploys `borg-backup-local-homelab.timer` (02:00), `borg-backup-local-photos.timer` (Mon 03:00), and `borg-backup-offsite.timer` (Sun 04:00).
- **`scripts/setup/docker/setup.sh`:** Deploys `docker-prune.timer` (Sun 03:30) and `homelab-containers.service` (lifecycle manager around Docker daemon).
- **`scripts/setup/wireguard/setup.sh`:** Deploys `wireguard-uptime.timer` (every 5 minutes) pushing health heartbeats to Uptime Kuma.

### 4. Monitoring & Management
- **Dozzle Dashboard (`logs.internal.pippinn.me`):** Real-time log streaming and one-click container actions without host shell access.
- **Beszel S.M.A.R.T. Monitoring (`monitoring.internal.pippinn.me`):** Containerized agent with `SYS_RAWIO` device passthrough tracking drive wear, temperatures, and S.M.A.R.T. health with email alerts.

---

## Deferred Items

| Item | New Target | Rationale |
|------|------------|-----------|
| **Immich ML to NAS** | **Milestone 23** | Kept running on the Raspberry Pi (`192.168.86.26:3003`) to ensure zero disruption during OS baseline cutover. Repatriation with iGPU/CPU acceleration planned in M23. |
| **Plex QuickSync Transcoding** | **Milestone 23** | Deferred to M23 alongside Immich ML to bundle GPU device passthrough (`/dev/dri`) validation. |
| **`.env` & `.secret.env` Normalization** | **Under Evaluation** | Skipped to avoid churn. Retaining the stable `vars.env` (tracked non-sensitive) + `.env` (gitignored secrets) model. |

---

## Verification & Documentation

- `ARCHITECTURE.md` updated with new hardware specifications, storage layout, backup strategy, and automation suites.
- `infrastructure/backup/README.md` updated to document native local Borg backup script and systemd timers.
- `infrastructure/wireguard/specs/02-uptime-monitoring/plan.md` updated with systemd timer deployment.
