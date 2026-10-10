#!/usr/bin/env bash
set -euo pipefail

# setup-snapraid-maintenance.sh
# Installs and enables the SnapRAID sync (daily 04:00) and scrub (weekly Sun 05:00)
# systemd services and timers.
#
# Usage:
#   sudo ./scripts/setup/snapraid/setup.sh

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (or with sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

echo "==> Verifying scripts exist and are executable..."
chmod +x "${SCRIPTS_DIR}/snapraid-sync.sh" "${SCRIPTS_DIR}/snapraid-scrub.sh"

echo "==> Deploying SnapRAID configuration..."
if [[ -f /etc/snapraid.conf ]]; then
    BACKUP_FILE="/etc/snapraid.conf.bak.$(date +%Y%m%d%H%M%S)"
    echo "Backing up existing /etc/snapraid.conf to ${BACKUP_FILE}..."
    cp /etc/snapraid.conf "${BACKUP_FILE}"
fi
cp "${SCRIPT_DIR}/snapraid.conf" /etc/snapraid.conf
chmod 644 /etc/snapraid.conf

echo "==> Copying systemd service and timer units..."
cp "${SCRIPT_DIR}/snapraid-sync.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/snapraid-sync.timer"   /etc/systemd/system/
cp "${SCRIPT_DIR}/snapraid-scrub.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/snapraid-scrub.timer"   /etc/systemd/system/

echo "==> Reloading systemd daemon..."
systemctl daemon-reload

echo "==> Enabling and starting SnapRAID timers..."
systemctl enable --now snapraid-sync.timer
systemctl enable --now snapraid-scrub.timer

echo "==> Active SnapRAID timers:"
systemctl list-timers snapraid-sync.timer snapraid-scrub.timer --no-pager

echo ""
echo "✅ SnapRAID sync and scrub timers successfully configured and active!"
