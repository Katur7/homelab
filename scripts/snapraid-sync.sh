#!/usr/bin/env bash
# snapraid-sync.sh — Automated SnapRAID sync with safety deletion threshold check
#
# Usage:
#   sudo /home/grimur/homelab/scripts/snapraid-sync.sh [--force]
#
# Override deletion threshold:
#   Pass --force OR touch /tmp/snapraid-sync.force before running.
#
# Notifications:
#   Configured via /etc/snapraid-notify.conf or environment variables:
#     NOTIFY_EMAIL="user@example.com"                                    (Email sent on errors/aborts)
#     UPTIME_KUMA_PUSH_URL_SYNC="http://192.168.86.26:3001/api/push/<id>" (Heartbeat ping on success)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/snapraid.conf"
NOTIFY_CONF="/etc/snapraid-notify.conf"
FORCE_FLAG_FILE="/tmp/snapraid-sync.force"

# Safety threshold: abort if more than DEL_THRESHOLD files are deleted
DEL_THRESHOLD="${SNAPRAID_DEL_THRESHOLD:-50}"
FORCE_SYNC=0

if [[ "${1:-}" == "--force" ]] || [[ -f "$FORCE_FLAG_FILE" ]]; then
    FORCE_SYNC=1
    rm -f "$FORCE_FLAG_FILE"
fi

# Load optional notification config
if [[ -f "$NOTIFY_CONF" ]]; then
    # shellcheck disable=SC1090
    source "$NOTIFY_CONF"
fi

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    logger -t snapraid-sync "$*"
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
    local push_url="${UPTIME_KUMA_PUSH_URL_SYNC:-${UPTIME_KUMA_PUSH_URL:-}}"
    if [[ -n "$push_url" ]]; then
        curl -fsS -m 10 --retry 2 "$push_url" >/dev/null 2>&1 || log "Warning: Failed to notify Uptime Kuma"
    fi
}

# 1. Root check
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root." >&2
    exit 1
fi

# 2. Config check
if [[ ! -f "$CONFIG_FILE" ]]; then
    msg="SnapRAID configuration file $CONFIG_FILE not found on $(hostname)."
    log "Error: $msg"
    notify_email "[SnapRAID] Configuration Error on $(hostname)" "$msg"
    exit 1
fi

# 3. Check if another SnapRAID instance is already running
if pgrep -x snapraid >/dev/null; then
    log "Warning: Another SnapRAID process is currently running. Exiting."
    exit 0
fi

# 4. Critical safety check: Ensure all disk mountpoints are active
# Prevents catastrophic parity corruption if a data or parity disk fails to mount.
DATA_DISKS=(/srv/disk1 /srv/disk2 /srv/disk3 /srv/parity1)
for mount_dir in "${DATA_DISKS[@]}"; do
    if ! mountpoint -q "$mount_dir"; then
        msg="CRITICAL: Mount point $mount_dir is not mounted on $(hostname)! Aborting SnapRAID sync to protect parity."
        log "$msg"
        notify_email "[SnapRAID CRITICAL] Mount Point Missing on $(hostname)" "$msg"
        exit 1
    fi
done

# 5. Pre-sync check: Inspect differences and deleted files count
log "Running snapraid diff..."
DIFF_OUTPUT=$(snapraid diff 2>&1 || true)

# Count removed files: lines starting with 'remove ' in diff output
DELETED_COUNT=$(echo "$DIFF_OUTPUT" | grep -c '^remove ' || true)

log "Diff check completed: ${DELETED_COUNT} files marked for removal (Threshold: ${DEL_THRESHOLD})."

if (( DELETED_COUNT > DEL_THRESHOLD )) && (( FORCE_SYNC == 0 )); then
    msg="ABORT: ${DELETED_COUNT} deleted files exceeds safety threshold of ${DEL_THRESHOLD} on $(hostname).\n\nTo force sync, run:\n  sudo touch ${FORCE_FLAG_FILE}\nand re-run sync.\n\nDiff Summary:\n$(echo "$DIFF_OUTPUT" | grep -E '^(remove|equal|add|update)' | head -n 40 || true)"
    log "$msg"
    notify_email "[SnapRAID WARNING] Deletion Threshold Exceeded on $(hostname)" "$msg"
    exit 2
fi

if (( FORCE_SYNC == 1 )) && (( DELETED_COUNT > DEL_THRESHOLD )); then
    log "Override flag detected: Proceeding with sync despite ${DELETED_COUNT} deleted files."
fi

# 6. Run SnapRAID sync
log "Starting snapraid sync..."
START_TIME=$(date +%s)

SYNC_OUTPUT=""
if SYNC_OUTPUT=$(snapraid sync 2>&1); then
    ELAPSED=$(( $(date +%s) - START_TIME ))
    log "SnapRAID sync completed successfully in ${ELAPSED}s."
    notify_kuma
else
    EXIT_CODE=$?
    ELAPSED=$(( $(date +%s) - START_TIME ))
    msg="SnapRAID sync failed with exit code ${EXIT_CODE} after ${ELAPSED}s on $(hostname).\n\nOutput:\n$(echo "$SYNC_OUTPUT" | tail -n 30)"
    log "$msg"
    notify_email "[SnapRAID FAILED] Sync Error on $(hostname)" "$msg"
    exit "$EXIT_CODE"
fi

exit 0
