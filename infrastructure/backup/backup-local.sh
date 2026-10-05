#!/bin/bash
set -euo pipefail

# backup-local.sh — Local BorgBackup for homelab config and Immich photos
#
# Usage:
#   sudo ./backup-local.sh [homelab|photos|all]
#
# Environment / Config:
#   Passphrase: /root/.borg-passphrase
#   Repo:       /mnt/storage/backup/borg2 (or /srv/disk2/backup/borg2)
#   Email:      /etc/snapraid-notify.conf (NOTIFY_EMAIL)

TARGET="${1:-homelab}"
PASSPHRASE_FILE="/root/.borg-passphrase"
NOTIFY_CONF="/etc/snapraid-notify.conf"

# Determine local repository path
if [[ -n "${BORG_REPO:-}" ]]; then
  REPO="$BORG_REPO"
elif [[ -d "/mnt/storage/backup/borg2" ]]; then
  REPO="/mnt/storage/backup/borg2"
elif [[ -d "/srv/disk2/backup/borg2" ]]; then
  REPO="/srv/disk2/backup/borg2"
else
  REPO="/mnt/storage/backup/borg2"
fi

export BORG_PASSCOMMAND="cat ${PASSPHRASE_FILE}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXCLUDE_FILE="${SCRIPT_DIR}/borg-exclude-homelab.txt"

# Load optional email notification config
NOTIFY_EMAIL=""
if [[ -f "$NOTIFY_CONF" ]]; then
  # shellcheck disable=SC1090
  source "$NOTIFY_CONF"
fi

log() {
  local msg="[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
  echo "$msg"
  logger -t borg-backup-local "$*"
}

notify_email() {
  local subject="$1"
  local body="$2"
  if [[ -n "${NOTIFY_EMAIL:-}" ]]; then
    if command -v mail >/dev/null 2>&1; then
      echo -e "$body" | mail -s "$subject" "$NOTIFY_EMAIL" || log "Warning: Failed to send email via mail"
    elif command -v msmtp >/dev/null 2>&1; then
      printf "Subject: %s\nTo: %s\n\n%s\n" "$subject" "$NOTIFY_EMAIL" "$body" | msmtp "$NOTIFY_EMAIL" || log "Warning: Failed to send email via msmtp"
    else
      log "Warning: Neither 'mail' nor 'msmtp' found to send alert email"
    fi
  fi
}

notify_kuma() {
  local job="$1"
  local push_url=""
  if [[ -f "/root/.uptime-kuma-push-local-${job}" ]]; then
    push_url="$(cat "/root/.uptime-kuma-push-local-${job}")"
  elif [[ -f "/root/.uptime-kuma-push-local" ]]; then
    push_url="$(cat "/root/.uptime-kuma-push-local")"
  fi

  if [[ -n "$push_url" ]]; then
    log "Pinging Uptime Kuma for local-${job}..."
    curl -fsS -m 10 --retry 3 "$push_url" >/dev/null 2>&1 || log "Warning: Failed to send Uptime Kuma push notification"
  fi
}

# Validation checks
if [[ $EUID -ne 0 ]]; then
  echo "Error: This script must be run as root." >&2
  exit 1
fi

if [[ ! -f "$PASSPHRASE_FILE" ]]; then
  msg="Borg passphrase file $PASSPHRASE_FILE not found on $(hostname)."
  log "Error: $msg"
  notify_email "[BorgBackup FAILED] Passphrase missing on $(hostname)" "$msg"
  exit 1
fi

if [[ ! -d "$REPO" ]]; then
  msg="Borg repository $REPO not found on $(hostname). Ensure /mnt/storage is mounted."
  log "Error: $msg"
  notify_email "[BorgBackup FAILED] Local repo missing on $(hostname)" "$msg"
  exit 1
fi

backup_homelab() {
  log "Starting local backup: homelab -> $REPO"
  local start_time
  start_time=$(date +%s)

  if ! borg create --stats \
      --exclude-from "$EXCLUDE_FILE" \
      "${REPO}::homelab-{now}" \
      /home/grimur/homelab/ 2>&1; then
    local exit_code=$?
    local msg="Borg local backup for homelab failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local homelab backup error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Pruning old homelab archives..."
  borg prune --stats --glob-archives 'homelab-*' \
    --keep-daily 14 --keep-weekly 8 --keep-monthly 12 \
    "$REPO"

  log "Compacting repository..."
  borg compact "$REPO"

  local elapsed=$(( $(date +%s) - start_time ))
  log "Local homelab backup completed successfully in ${elapsed}s."
  notify_kuma "homelab"
}

backup_photos() {
  log "Starting local backup: immich_photos -> $REPO"
  local start_time
  start_time=$(date +%s)
  local photos_dir="/mnt/storage/photos"

  if [[ ! -d "$photos_dir" ]]; then
    local msg="Photos directory $photos_dir does not exist or storage is unmounted on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Photos dir missing on $(hostname)" "$msg"
    return 1
  fi

  if ! borg create --stats \
      "${REPO}::immich_photos-{now}" \
      "$photos_dir" 2>&1; then
    local exit_code=$?
    local msg="Borg local backup for immich_photos failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local photos backup error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Pruning old photos archives..."
  borg prune --stats --glob-archives 'immich_photos-*' \
    --keep-weekly 8 --keep-monthly 12 --keep-yearly 2 \
    "$REPO"

  log "Compacting repository..."
  borg compact "$REPO"

  local elapsed=$(( $(date +%s) - start_time ))
  log "Local photos backup completed successfully in ${elapsed}s."
  notify_kuma "photos"
}

case "$TARGET" in
  homelab)
    backup_homelab
    ;;
  photos)
    backup_photos
    ;;
  all)
    backup_homelab
    backup_photos
    ;;
  *)
    echo "Usage: $0 [homelab|photos|all]" >&2
    exit 1
    ;;
esac

exit 0
