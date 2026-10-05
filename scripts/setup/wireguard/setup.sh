#!/usr/bin/env bash
set -euo pipefail

# setup-wireguard-uptime.sh
# Installs and enables the WireGuard Uptime Kuma heartbeat monitor systemd timer (every 5 minutes).
#
# Usage:
#   sudo ./scripts/setup/wireguard/setup.sh

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (or with sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
CHECK_SCRIPT="${REPO_DIR}/infrastructure/wireguard/scripts/uptime-push.sh"
PUSH_URL_FILE="/root/.uptime-kuma-push-wireguard"

echo "==> 1. Verifying health check script..."
if [[ ! -f "$CHECK_SCRIPT" ]]; then
    echo "Error: Check script not found at $CHECK_SCRIPT" >&2
    exit 1
fi
chmod +x "$CHECK_SCRIPT"

echo "==> 2. Verifying Uptime Kuma push secret..."
if [[ ! -f "$PUSH_URL_FILE" ]]; then
    echo "Warning: $PUSH_URL_FILE not found." >&2
    echo "  Create this file with your Uptime Kuma push monitor URL:" >&2
    echo "  echo 'http://192.168.86.26:3001/api/push/<token>?status=up&msg=OK&ping=' > $PUSH_URL_FILE" >&2
    echo "  chmod 600 $PUSH_URL_FILE" >&2
else
    chmod 600 "$PUSH_URL_FILE"
    echo "Push URL file confirmed with permissions 0600."
fi

echo "==> 3. Testing health check execution..."
if "$CHECK_SCRIPT"; then
    echo "Health check succeeded!"
else
    echo "Notice: Health check script exited with non-zero status (WireGuard container may currently be stopped)."
    echo "Proceeding with service and timer installation..."
fi

echo "==> 4. Copying systemd service and timer units..."
cp "${SCRIPT_DIR}/wireguard-uptime.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/wireguard-uptime.timer"   /etc/systemd/system/

echo "==> 5. Reloading systemd daemon..."
systemctl daemon-reload

echo "==> 6. Enabling and starting WireGuard uptime timer..."
systemctl enable --now wireguard-uptime.timer

echo "==> 7. Active WireGuard uptime timer:"
systemctl list-timers wireguard-uptime.timer --no-pager

echo ""
echo "✅ WireGuard uptime monitoring timer successfully configured and active!"
echo "   Fires every 5 minutes (logs available via: journalctl -u wireguard-uptime.service)"
