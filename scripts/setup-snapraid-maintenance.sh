#!/usr/bin/env bash
set -euo pipefail

# setup-snapraid-maintenance.sh
# Installs and enables the SnapRAID sync (daily 04:00) and scrub (weekly Sun 05:00)
# systemd services and timers.
#
# Usage:
#   sudo ./scripts/setup-snapraid-maintenance.sh

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (or with sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Verifying scripts exist and are executable..."
chmod +x "${SCRIPT_DIR}/snapraid-sync.sh" "${SCRIPT_DIR}/snapraid-scrub.sh"

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
