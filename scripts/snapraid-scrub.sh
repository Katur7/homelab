#!/usr/bin/env bash
# snapraid-scrub.sh — Automated weekly SnapRAID scrub
#
# Usage:
#   sudo /home/grimur/homelab/scripts/snapraid-scrub.sh [percentage]
#
# Notifications:
#   Configured via /etc/snapraid-notify.conf or environment variables:
#     NOTIFY_EMAIL="user@example.com"                                      (Email sent on errors)
#     UPTIME_KUMA_PUSH_URL_SCRUB="http://192.168.86.26:3001/api/push/<id>" (Heartbeat ping on success)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="/etc/snapraid.conf"
NOTIFY_CONF="/etc/snapraid-notify.conf"

# Default to scrubbing 5% of the array older than 10 days
SCRUB_PERCENT="${1:-${SNAPRAID_SCRUB_PERCENT:-5}}"

# Load optional notification config
if [[ -f "$NOTIFY_CONF" ]]; then
    # shellcheck disable=SC1090
    source "$NOTIFY_CONF"
fi

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    logger -t snapraid-scrub "$*"
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
    local push_url="${UPTIME_KUMA_PUSH_URL_SCRUB:-${UPTIME_KUMA_PUSH_URL:-}}"
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
DATA_DISKS=(/srv/disk1 /srv/disk2 /srv/disk3 /srv/parity1)
for mount_dir in "${DATA_DISKS[@]}"; do
    if ! mountpoint -q "$mount_dir"; then
        msg="CRITICAL: Mount point $mount_dir is not mounted on $(hostname)! Aborting SnapRAID scrub."
        log "$msg"
        notify_email "[SnapRAID CRITICAL] Mount Point Missing on $(hostname)" "$msg"
        exit 1
    fi
done

# 5. Run SnapRAID scrub
log "Starting snapraid scrub (${SCRUB_PERCENT}% of array)..."
START_TIME=$(date +%s)

SCRUB_OUTPUT=""
if SCRUB_OUTPUT=$(snapraid scrub -p "$SCRUB_PERCENT" -o 10 2>&1); then
    ELAPSED=$(( $(date +%s) - START_TIME ))
    log "SnapRAID scrub (${SCRUB_PERCENT}%) completed successfully in ${ELAPSED}s."
    notify_kuma
else
    EXIT_CODE=$?
    ELAPSED=$(( $(date +%s) - START_TIME ))
    msg="SnapRAID scrub failed with exit code ${EXIT_CODE} after ${ELAPSED}s on $(hostname).\n\nOutput:\n$(echo "$SCRUB_OUTPUT" | tail -n 30)"
    log "$msg"
    notify_email "[SnapRAID FAILED] Scrub Error on $(hostname)" "$msg"
    exit "$EXIT_CODE"
fi

exit 0
