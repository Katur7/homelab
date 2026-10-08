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
export BORG_LOCK_WAIT="${BORG_LOCK_WAIT:-900}"
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
  local exit_code=0

  borg create --stats \
      --exclude-from "$EXCLUDE_FILE" \
      "${REPO}::homelab-{now}" \
      /home/grimur/homelab/ || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg local backup for homelab failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local homelab backup error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Pruning old homelab archives..."
  exit_code=0
  borg prune --stats --glob-archives 'homelab-*' \
    --keep-daily 14 --keep-weekly 8 --keep-monthly 12 \
    "$REPO" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg prune for homelab failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local homelab prune error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Compacting repository..."
  exit_code=0
  borg compact "$REPO" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg compact for homelab failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local homelab compact error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  local elapsed=$(( $(date +%s) - start_time ))
  log "Local homelab backup completed successfully in ${elapsed}s."
  notify_kuma "homelab"
}

backup_photos() {
  log "Starting local backup: immich_photos -> $REPO"
  local start_time
  start_time=$(date +%s)
  local photos_dir="/mnt/storage/photos"
  local exit_code=0

  if [[ ! -d "$photos_dir" ]]; then
    local msg="Photos directory $photos_dir does not exist or storage is unmounted on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Photos dir missing on $(hostname)" "$msg"
    return 1
  fi

  borg create --stats \
      "${REPO}::immich_photos-{now}" \
      "$photos_dir" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg local backup for immich_photos failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local photos backup error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Pruning old photos archives..."
  exit_code=0
  borg prune --stats --glob-archives 'immich_photos-*' \
    --keep-weekly 8 --keep-monthly 12 --keep-yearly 2 \
    "$REPO" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg prune for immich_photos failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local photos prune error on $(hostname)" "$msg"
    return "$exit_code"
  fi

  log "Compacting repository..."
  exit_code=0
  borg compact "$REPO" || exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    local msg="Borg compact for immich_photos failed with exit code ${exit_code} on $(hostname)."
    log "Error: $msg"
    notify_email "[BorgBackup FAILED] Local photos compact error on $(hostname)" "$msg"
    return "$exit_code"
  fi

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
    rc=0
    backup_homelab || rc=$?
    backup_photos || rc=$?
    exit "$rc"
    ;;
  *)
    echo "Usage: $0 [homelab|photos|all]" >&2
    exit 1
    ;;
esac
