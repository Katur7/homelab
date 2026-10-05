#!/usr/bin/env bash
set -euo pipefail

# setup-borg-backup.sh
# Validates prerequisites and installs the Borg backup systemd services & timers
# for both local NAS backups (homelab daily, photos weekly) and offsite pi-backup (weekly).
#
# Usage:
#   sudo ./scripts/setup/borg/setup.sh

if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (or with sudo)." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LOCAL_BACKUP_SCRIPT="${REPO_DIR}/infrastructure/backup/backup-local.sh"
OFFSITE_BACKUP_SCRIPT="${REPO_DIR}/infrastructure/backup/backup-to-pi.sh"
PASSPHRASE_FILE="/root/.borg-passphrase"
SSH_KEY_FILE="/root/.ssh/id_ed25519_backup_pi"

echo "==> 1. Checking BorgBackup installation..."
if ! command -v borg >/dev/null 2>&1; then
    echo "BorgBackup is not installed. Installing via apt..."
    apt update && apt install -y borgbackup
else
    echo "BorgBackup is installed: $(borg --version)"
fi

echo "==> 2. Verifying backup scripts..."
for script in "$LOCAL_BACKUP_SCRIPT" "$OFFSITE_BACKUP_SCRIPT"; do
    if [[ ! -f "$script" ]]; then
        echo "Error: Backup script not found at $script" >&2
        exit 1
    fi
    chmod +x "$script"
done

echo "==> 3. Verifying encryption passphrase & SSH key..."
if [[ ! -f "$PASSPHRASE_FILE" ]]; then
    echo "Error: $PASSPHRASE_FILE does not exist!" >&2
    echo "Please create $PASSPHRASE_FILE with your Borg repository passphrase:" >&2
    echo "  echo 'your-passphrase' > $PASSPHRASE_FILE && chmod 600 $PASSPHRASE_FILE" >&2
    exit 1
fi
chmod 600 "$PASSPHRASE_FILE"

if [[ -f "$SSH_KEY_FILE" ]]; then
    chmod 600 "$SSH_KEY_FILE"
else
    echo "Notice: SSH key $SSH_KEY_FILE for pi-backup not found."
    echo "  Offsite backups will fail until this key is installed."
fi

echo "==> 4. Verifying local repository..."
LOCAL_REPO="/mnt/storage/backup/borg2"
if [[ -d "$LOCAL_REPO" ]] || [[ -d "/srv/disk2/backup/borg2" ]]; then
    echo "Local Borg repository confirmed."
else
    echo "Notice: Local Borg repository not found at $LOCAL_REPO."
    echo "  Ensure storage pool is mounted, or initialize repo with:"
    echo "  BORG_PASSCOMMAND='cat $PASSPHRASE_FILE' borg init --encryption=repokey-blake2 $LOCAL_REPO"
fi

echo "==> 5. Installing systemd service and timer units..."
cp "${SCRIPT_DIR}/borg-backup-local-homelab.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-homelab.timer"   /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-photos.service"  /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-photos.timer"    /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-offsite.service"       /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-offsite.timer"         /etc/systemd/system/

echo "==> 6. Reloading systemd daemon..."
systemctl daemon-reload

echo "==> 7. Enabling and starting Borg backup timers..."
systemctl enable --now borg-backup-local-homelab.timer
systemctl enable --now borg-backup-local-photos.timer
systemctl enable --now borg-backup-offsite.timer

echo "==> 8. Active Borg backup timers:"
systemctl list-timers borg-backup-*.timer --no-pager

echo ""
echo "✅ All Borg backup timers successfully configured and active!"
echo "   - Local Homelab: Daily 02:00 (borg-backup-local-homelab.timer)"
echo "   - Local Photos:  Mon   03:00 (borg-backup-local-photos.timer)"
echo "   - Offsite Pi:    Sun   04:00 (borg-backup-offsite.timer)"
