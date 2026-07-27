#!/bin/bash
set -euo pipefail

export BORG_PASSCOMMAND='cat /root/.borg-passphrase'
export BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi'
REPO="ssh://borg@pi-backup/mnt/backup/borg-repo"
RATE=10000  # ~10 MB/s

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "Starting offsite backup to pi-backup"

# homelab
log "Creating homelab archive"
borg create --stats \
  --upload-ratelimit "$RATE" \
  --exclude-from /home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt \
  "$REPO::homelab-{now}" \
  /home/grimur/homelab/

borg prune --stats --glob-archives 'homelab-*' \
  --keep-daily 14 --keep-weekly 8 --keep-monthly 12 \
  "$REPO"

# immich_photos (includes built-in DB dump at photos/backups/)
log "Creating immich_photos archive"
borg create --stats \
  --upload-ratelimit "$RATE" \
  "$REPO::immich_photos-{now}" \
  /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos

borg prune --stats --glob-archives 'immich_photos-*' \
  --keep-weekly 8 --keep-monthly 12 --keep-yearly 2 \
  "$REPO"

borg compact "$REPO"

log "Offsite backup complete"
