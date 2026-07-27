# Backup

## Overview

Two-tier borg backup strategy for the NAS:

| Tier | Destination | Schedule | Covers |
|------|-------------|----------|--------|
| Local | Borg repo on NAS (OMV plugin) | Daily 02:00 | `homelab/` repo + app state + Immich photos |
| Offsite | `pi-backup` (parents' house, via Tailscale) | Weekly Sun 04:00 | `homelab/` repo + Immich photos |

Both repos use `repokey-blake2` encryption. Passphrase in `/root/.borg-passphrase` on NAS.

## What's backed up

### `homelab` archive
- Source: `/home/grimur/homelab/`
- Contains: compose files, configs, app state directories, `.env` secrets
- Excludes: hot databases, caches, logs — see [borg-exclude-homelab.txt](borg-exclude-homelab.txt)
- Retention (offsite): 14 daily / 8 weekly / 12 monthly

### `immich_photos` archive (offsite only)
- Source: `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos`
- Contains: all Immich photos/videos + Immich's built-in DB dumps (`backups/`)
- Retention: 8 weekly / 12 monthly / 2 yearly

## Files

| File | Purpose |
|------|---------|
| `backup-to-pi.sh` | Offsite push script — create, prune, compact |
| `borg-exclude-homelab.txt` | Exclusion patterns for the homelab archive |

## Host-managed files (not in git)

| File | Host | Purpose |
|------|------|---------|
| `/root/.borg-passphrase` | NAS | Borg encryption passphrase |
| `/root/.ssh/id_ed25519_backup_pi` | NAS | SSH key for borg user on pi-backup |
| `/etc/cron.d/backup-to-pi` | NAS | Weekly cron schedule |
| `/home/borg/.ssh/authorized_keys` | pi-backup | Forced `borg serve` — restricts to repo path |

## Check if backup is working

```bash
# List offsite archives
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg list ssh://borg@pi-backup/mnt/backup/borg-repo

# Check last cron run
tail -50 /var/log/backup-to-pi.log

# Check local backup (OMV plugin)
# OMV UI → Services → BorgBackup → view repo/logs
```

## Run backup manually

```bash
# Offsite (run as root, use tmux for long runs)
sudo /home/grimur/homelab/infrastructure/backup/backup-to-pi.sh 2>&1 | tee /var/log/backup-to-pi.log

# Local only — use OMV BorgBackup plugin UI to trigger manually
```

## Restore

### List and extract from offsite repo

All restore commands run on the **NAS as root**. `borg extract` recreates the
full directory tree under the current working directory.

```bash
export BORG_PASSCOMMAND='cat /root/.borg-passphrase'
export BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi'
REPO="ssh://borg@pi-backup/mnt/backup/borg-repo"

# List archives
borg list "$REPO"

# List files in a specific archive
borg list "$REPO::homelab-2026-07-27T18:10:55"

# Extract full archive — recreates e.g. ./home/grimur/homelab/...
cd /tmp/restore
borg extract "$REPO::homelab-2026-07-27T18:10:55"

# Extract specific path only
borg extract "$REPO::homelab-2026-07-27T18:10:55" home/grimur/homelab/services/vikunja/

# Extract to original location (restores files in-place)
cd /
borg extract "$REPO::homelab-2026-07-27T18:10:55"

# Mount archive as read-only filesystem (browse before extracting)
mkdir /tmp/borg-mount
borg mount "$REPO::homelab-2026-07-27T18:10:55" /tmp/borg-mount
ls /tmp/borg-mount/
# When done:
borg umount /tmp/borg-mount
```

### Restore Immich photos

```bash
# Extract to staging area first (creates ./srv/dev-disk-by-uuid-.../photos/)
cd /tmp/restore
borg extract "$REPO::immich_photos-2026-07-27T18:11:34"

# Or restore in-place directly
cd /
borg extract "$REPO::immich_photos-2026-07-27T18:11:34"
```

### If NAS is lost (disaster recovery)

1. Install borg on a new machine
2. Copy `/root/.borg-passphrase` and SSH key from password manager
3. Access the offsite repo via Tailscale: `ssh://borg@pi-backup/mnt/backup/borg-repo`
4. Extract the latest `homelab` archive to restore all configs and `.env` files
5. Extract `immich_photos` archive to restore photos + DB dumps
6. Rebuild containers with `docker compose up -d` per service
