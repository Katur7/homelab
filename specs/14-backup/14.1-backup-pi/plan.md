# Milestone 14.1: Backup Pi Configuration & Borg Repo

## Goal

Configure the offsite backup Pi (Phase 6 from spec 14) — OS hardening, log2ram,
borg repo setup, and a validated test backup from the NAS over Tailscale.

---

## Infrastructure Context

| Item                | Value                                                        |
| ------------------- | ------------------------------------------------------------ |
| Pi model            | Raspberry Pi 4, 4GB RAM                                      |
| OS                  | Raspberry Pi OS Lite (Debian-based)                          |
| SD card             | 24GB                                                         |
| External storage    | 4TB 2.5" HDD, USB-attached, mounted at `/mnt/backup` (fstab) |
| Hostname            | `pi-backup`                                                  |
| User                | `backup` (existing admin user)                               |
| Network             | Behind parents' router, accessible via Tailscale only        |
| Pi Tailscale IP     | `100.110.206.9`                                              |
| NAS Tailscale       | `network_mode: host` container — NAS host has direct tailnet access |
| SSH                 | Traditional SSH with key auth (`ssh backup@pi-backup`)       |
| Parents' uplink     | Fiber (speed unknown, assume >= 50 Mbps up)                  |
| NAS Borg repo       | `.../backup/borg2` (repokey-blake2)                          |
| NAS Borg passphrase | Password manager + OMV plugin UI                             |

---

## Phase 1 — OS Hardening & log2ram

### 1.1 Verify unattended-upgrades

```bash
# Confirm the service is enabled and running
sudo systemctl status unattended-upgrades

# Confirm auto-update is enabled (should show "1" for both)
cat /etc/apt/apt.conf.d/20auto-upgrades
# Expected:
#   APT::Periodic::Update-Package-Lists "1";
#   APT::Periodic::Unattended-Upgrade "1";
```

If `20auto-upgrades` doesn't exist or shows "0":
```bash
sudo dpkg-reconfigure -plow unattended-upgrades
# Select "Yes"
```

Optional — enable auto-reboot for kernel updates (Pi is headless, no one to
manually reboot):
```bash
sudo tee -a /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Automatic-Reboot "true";
Unattended-Upgrade::Automatic-Reboot-Time "05:00";
EOF
```

### 1.2 Install log2ram

Reduces SD card writes by keeping `/var/log` in RAM, flushing periodically.

```bash
echo "deb [signed-by=/usr/share/keyrings/azlux-archive-keyring.gpg] http://packages.azlux.fr/debian/ bookworm main" | sudo tee /etc/apt/sources.list.d/azlux.list
sudo wget -O /usr/share/keyrings/azlux-archive-keyring.gpg https://azlux.fr/repo.gpg
sudo apt update
sudo apt install log2ram
```

Configure size (40MB default is fine for 24GB SD):
```bash
# /etc/log2ram.conf — verify SIZE=40M, no changes needed
cat /etc/log2ram.conf
```

Reboot to activate:
```bash
sudo reboot
```

After reboot, verify:
```bash
df -h /var/log
# Should show log2ram tmpfs mount
```

### 1.3 Basic hardening

The Pi is only accessible via Tailscale (not exposed to the internet), so
the attack surface is minimal. Minimal hardening:

```bash
# Ensure SSH password auth is disabled (key-only)
grep -i PasswordAuthentication /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null
# If not explicitly set to "no":
echo "PasswordAuthentication no" | sudo tee /etc/ssh/sshd_config.d/99-hardening.conf
sudo systemctl reload sshd
```

---

## Phase 2 — Borg & User Setup on Pi

### 2.1 Install borg

```bash
sudo apt install borgbackup
borg --version  # Confirm >= 1.2
```

### 2.2 Create dedicated borg user

```bash
sudo useradd -r -m -d /home/borg -s /bin/bash borg
sudo usermod -L borg  # Lock password (no password login)
```

Note: shell must be `/bin/bash` (or at least a real shell) because `borg serve`
needs it. The forced-command in `authorized_keys` restricts what can run.

### 2.3 Create repo directory

```bash
sudo mkdir -p /mnt/backup/borg-repo
sudo chown borg:borg /mnt/backup/borg-repo
sudo chmod 700 /mnt/backup/borg-repo
```

### 2.4 Set up SSH authorized_keys for borg user

On the NAS, generate an SSH keypair for root (if none exists):
```bash
# On NAS as root
sudo ssh-keygen -t ed25519 -C "nas-to-backup-pi" -f /root/.ssh/id_ed25519_backup_pi -N ""
```

Copy the public key, then on the Pi:
```bash
sudo mkdir -p /home/borg/.ssh
sudo chmod 700 /home/borg/.ssh

# Add the NAS public key with forced-command restriction
sudo tee /home/borg/.ssh/authorized_keys <<'EOF'
command="borg serve --restrict-to-repository /mnt/backup/borg-repo",restrict SSH_PUBLIC_KEY_HERE
EOF

sudo chmod 600 /home/borg/.ssh/authorized_keys
sudo chown -R borg:borg /home/borg/.ssh
```

The `restrict` keyword disables pty, agent-forwarding, X11-forwarding, and
port-forwarding in one directive (OpenSSH >= 7.2).

Test SSH connectivity from NAS:
```bash
# On NAS as root
ssh -i /root/.ssh/id_ed25519_backup_pi borg@pi-backup
# Should see something like "borg serve" output or connection close — NOT a shell
```

---

## Phase 3 — Initialize Borg Repo

From the NAS as root:

### 3.1 Create passphrase file on NAS

```bash
# /root/.borg-passphrase should contain the borg passphrase (same as borg2 repo)
# Set via password manager — never committed to git
cat > /root/.borg-passphrase <<'EOF'
YOUR_PASSPHRASE_HERE
EOF
chmod 600 /root/.borg-passphrase
```

If this file already exists from Phase 5 (desktop) work, skip this step.

### 3.2 Init remote repo

```bash
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg init --encryption=repokey-blake2 \
  ssh://borg@pi-backup/mnt/backup/borg-repo
```

Verify:
```bash
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg info ssh://borg@pi-backup/mnt/backup/borg-repo
# Should show: Encrypted: Yes (repokey BLAKE2b)
```

---

## Phase 4 — Test Backup

### 4.1 Manual test — homelab archive

```bash
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg create --stats --progress \
  --upload-ratelimit 10000 \
  --exclude-from /home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt \
  "ssh://borg@pi-backup/mnt/backup/borg-repo::homelab-{now}" \
  /home/grimur/homelab/
```

Note: `--upload-ratelimit 10000` = ~10 MB/s. Adjust after observing first run.

### 4.2 Manual test — immich_photos archive

```bash
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg create --stats --progress \
  --upload-ratelimit 10000 \
  "ssh://borg@pi-backup/mnt/backup/borg-repo::immich_photos-{now}" \
  /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos
```

Warning: first run is a full backup (~28GB+ for photos). Will take time even
at 10 MB/s. Consider running in tmux/screen.

### 4.3 Verify

```bash
BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi' \
borg list ssh://borg@pi-backup/mnt/backup/borg-repo
# Should show both test archives
```

---

## Phase 5 — Automated Push Script & Schedule

### 5.1 Create NAS-side wrapper script

Create `/usr/local/bin/backup-to-pi.sh` on the NAS:

```bash
#!/bin/bash
set -euo pipefail

export BORG_PASSCOMMAND='cat /root/.borg-passphrase'
export BORG_RSH='ssh -i /root/.ssh/id_ed25519_backup_pi'
REPO="ssh://borg@pi-backup/mnt/backup/borg-repo"
RATE=10000  # ~10 MB/s

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

log "Starting offsite backup to pi-backup"

# homelab
log "Creating homelab archive"
borg create --stats \
  --upload-ratelimit "$RATE" \
  --exclude-from /home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt \
  "$REPO::homelab-{now}" \
  /home/grimur/homelab/

borg prune --stats --glob-archives 'homelab-*' \
  --keep-daily 14 --keep-weekly 8 --keep-monthly 12 \
  "$REPO"

# immich_photos (includes built-in DB dump at photos/backups/)
log "Creating immich_photos archive"
borg create --stats \
  --upload-ratelimit "$RATE" \
  "$REPO::immich_photos-{now}" \
  /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos

borg prune --stats --glob-archives 'immich_photos-*' \
  --keep-weekly 8 --keep-monthly 12 --keep-yearly 2 \
  "$REPO"

borg compact "$REPO"

log "Offsite backup complete"
```

```bash
sudo chmod 700 /usr/local/bin/backup-to-pi.sh
```

### 5.2 Schedule via cron on NAS

```bash
# Weekly Sunday 04:00 (after local borg jobs finish)
echo '0 4 * * 0 root /usr/local/bin/backup-to-pi.sh >> /var/log/backup-to-pi.log 2>&1' \
  | sudo tee /etc/cron.d/backup-to-pi
```

### 5.3 Test automated run

```bash
sudo /usr/local/bin/backup-to-pi.sh
```

---

## Phase 6 — Verify HDD Health Monitoring

The 4TB HDD is critical infrastructure. Set up basic SMART monitoring:

```bash
# On Pi
sudo apt install smartmontools
sudo smartctl -a /dev/sda  # Confirm SMART is enabled

# Enable weekly SMART self-test (short)
# smartd is usually enabled by default after install
sudo systemctl enable --now smartd
```

---

## Rollback

| Phase            | Rollback                                                                |
| ---------------- | ----------------------------------------------------------------------- |
| 1 (OS hardening) | Remove log2ram: `sudo apt remove log2ram`                               |
| 2 (borg user)    | `sudo userdel -r borg`                                                  |
| 3 (repo init)    | `sudo rm -rf /mnt/backup/borg-repo`                                     |
| 5 (cron)         | `sudo rm /etc/cron.d/backup-to-pi` and `/usr/local/bin/backup-to-pi.sh` |

---

## Open Items

- Exact upload rate limit — tune after first run based on observed speed
- Failure notifications — deferred to Phase 7 of parent spec 14
- `borg check` schedule — deferred to Phase 7 of parent spec 14
- Whether to add `borg compact` to the wrapper (included above, can remove if slow)

---

## Files Changed / Created

| File                                     | Location           | Action                    |
| ---------------------------------------- | ------------------ | ------------------------- |
| `specs/14-backup/14.1-backup-pi/plan.md` | Repo               | This file                 |
| `infrastructure/tailscale/compose.yaml`  | Repo               | Changed to `network_mode: host` |
| `/usr/local/bin/backup-to-pi.sh`         | NAS (host-managed) | New — Phase 5             |
| `/etc/cron.d/backup-to-pi`               | NAS (host-managed) | New — Phase 5             |
| `/root/.ssh/id_ed25519_backup_pi`        | NAS (host-managed) | New — Phase 2             |
| `/root/.borg-passphrase`                 | NAS (host-managed) | New or existing — Phase 3 |
