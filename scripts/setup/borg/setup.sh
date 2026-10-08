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
PI_BACKUP_HOST="pi-backup"
PI_BACKUP_IP="100.110.206.9"
KNOWN_HOSTS_FILE="/root/.ssh/known_hosts"

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

echo "==> 4. Configuring offsite host resolution (/etc/hosts)..."
if grep -q -E "^[[:space:]]*${PI_BACKUP_IP}[[:space:]]+.*\\b${PI_BACKUP_HOST}\\b" /etc/hosts; then
    echo "  ${PI_BACKUP_HOST} (${PI_BACKUP_IP}) already configured in /etc/hosts."
elif grep -q -E "\\b${PI_BACKUP_HOST}\\b" /etc/hosts; then
    echo "  Updating existing ${PI_BACKUP_HOST} entry in /etc/hosts to ${PI_BACKUP_IP}..."
    sed -i -E "s/^[0-9.]+[[:space:]]+.*\\b${PI_BACKUP_HOST}\\b.*/${PI_BACKUP_IP}\t${PI_BACKUP_HOST}/" /etc/hosts
else
    echo "  Adding ${PI_BACKUP_IP} ${PI_BACKUP_HOST} to /etc/hosts..."
    printf "%s\t%s\n" "${PI_BACKUP_IP}" "${PI_BACKUP_HOST}" >> /etc/hosts
fi

echo "==> 5. Configuring SSH known_hosts for ${PI_BACKUP_HOST}..."
mkdir -p /root/.ssh
chmod 700 /root/.ssh
touch "$KNOWN_HOSTS_FILE"
chmod 644 "$KNOWN_HOSTS_FILE"

if ssh-keygen -F "${PI_BACKUP_HOST}" -f "$KNOWN_HOSTS_FILE" >/dev/null 2>&1; then
    echo "  Host key for ${PI_BACKUP_HOST} already present in ${KNOWN_HOSTS_FILE}."
else
    echo "  Scanning host keys for ${PI_BACKUP_HOST}..."
    SCANNED_KEY=$(ssh-keyscan -T 5 -H "${PI_BACKUP_HOST}" 2>/dev/null || true)
    if [[ -n "$SCANNED_KEY" ]]; then
        echo "$SCANNED_KEY" >> "$KNOWN_HOSTS_FILE"
        echo "  Successfully added ${PI_BACKUP_HOST} host key to ${KNOWN_HOSTS_FILE}."
    else
        echo "  Notice: Could not reach ${PI_BACKUP_HOST} via ssh-keyscan."
        echo "    Ensure Tailscale is connected and ${PI_BACKUP_HOST} (${PI_BACKUP_IP}) is online."
        echo "    You can populate it manually once online: ssh-keyscan -H ${PI_BACKUP_HOST} >> ${KNOWN_HOSTS_FILE}"
    fi
fi

if ! ssh-keygen -F "${PI_BACKUP_IP}" -f "$KNOWN_HOSTS_FILE" >/dev/null 2>&1; then
    SCANNED_IP_KEY=$(ssh-keyscan -T 5 -H "${PI_BACKUP_IP}" 2>/dev/null || true)
    if [[ -n "$SCANNED_IP_KEY" ]]; then
        echo "$SCANNED_IP_KEY" >> "$KNOWN_HOSTS_FILE"
    fi
fi

echo "==> 6. Verifying local repository..."
LOCAL_REPO="/mnt/storage/backup/borg2"
if [[ -d "$LOCAL_REPO" ]] || [[ -d "/srv/disk2/backup/borg2" ]]; then
    echo "Local Borg repository confirmed."
else
    echo "Notice: Local Borg repository not found at $LOCAL_REPO."
    echo "  Ensure storage pool is mounted, or initialize repo with:"
    echo "  BORG_PASSCOMMAND='cat $PASSPHRASE_FILE' borg init --encryption=repokey-blake2 $LOCAL_REPO"
fi

echo "==> 7. Installing systemd service and timer units..."
cp "${SCRIPT_DIR}/borg-backup-local-homelab.service" /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-homelab.timer"   /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-photos.service"  /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-local-photos.timer"    /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-offsite.service"       /etc/systemd/system/
cp "${SCRIPT_DIR}/borg-backup-offsite.timer"         /etc/systemd/system/

echo "==> 8. Reloading systemd daemon..."
systemctl daemon-reload

echo "==> 9. Enabling and starting Borg backup timers..."
systemctl enable --now borg-backup-local-homelab.timer
systemctl enable --now borg-backup-local-photos.timer
systemctl enable --now borg-backup-offsite.timer

echo "==> 10. Active Borg backup timers:"
systemctl list-timers borg-backup-*.timer --no-pager

echo ""
echo "✅ All Borg backup timers successfully configured and active!"
echo "   - Local Homelab: Daily 02:00 (borg-backup-local-homelab.timer)"
echo "   - Local Photos:  Mon   03:00 (borg-backup-local-photos.timer)"
echo "   - Offsite Pi:    Sun   04:00 (borg-backup-offsite.timer)"
