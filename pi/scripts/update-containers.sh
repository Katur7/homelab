#!/bin/bash
# update-containers.sh
# Pulls latest images and restarts all Pi stacks.
# Runs weekly via cron. Logs to syslog via logger.
#
# Cron entry (crontab -e):
#   0 3 * * 3 /home/grimur/homelab/pi/scripts/update-containers.sh

set -uo pipefail

HOMELAB_DIR="/home/grimur/homelab"
STACKS=("pihole" "uptime-kuma")

log() { logger -t container-update "$*"; }

log "=== Container update started ==="

# Pull latest repo config before updating containers
log "Pulling latest repo config..."
if ! git -C "$HOMELAB_DIR" pull; then
    log "WARNING: git pull failed — continuing with existing config"
fi

# Update each stack independently — one failure does not block the others
for stack in "${STACKS[@]}"; do
    dir="$HOMELAB_DIR/pi/services/$stack"
    log "--- Updating $stack ---"
    if cd "$dir" && docker compose pull && docker compose up -d --remove-orphans; then
        log "$stack updated successfully"
    else
        log "ERROR: $stack update failed"
    fi
done

log "=== Container update complete ==="
