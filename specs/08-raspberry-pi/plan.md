# Milestone 08 Plan: Raspberry Pi — Documentation, Hardening & Maintenance

**Date:** 2026-03-29
**Status:** `IN PROGRESS`

---

## Overview

The Raspberry Pi is a secondary host running three services: backup PiHole, Nebula-Sync
(PiHole config sync), and UptimeKuma. It has no presence in this repo and no defined
maintenance posture. This milestone documents all Pi services under GitOps-Lite, hardens
the OS, establishes auto-patching for OS packages, and adds Docker image update monitoring.

**Pi services inventory:**

| Service | Role | Port |
|---------|------|------|
| `pihole` | Backup DNS resolver (secondary to NAS PiHole) | 53 (DNS), 80 (web UI) |
| `nebula-sync` | Syncs PiHole config from primary to backup | Internal only |
| `uptime-kuma` | LAN service monitoring | 3001 |

---

## Sub-Milestones

---

### 08.1 — Publish Repo ✅

**Goal:** Audit and publish the homelab repo publicly on GitHub.

**Status:** Complete — see commit `106f84f`.

---

### 08.2 — Pi Repo Structure & Service Documentation

**Goal:** Bring the Pi into the repo as a documented, GitOps-managed host.

**Proposed structure:**

```
pi/
  README.md                  # Pi host overview, IP, role, deployment notes
  global.env                 # Pi-wide vars: PUID, PGID, TZ, PI_IP
  services/
    pihole/
      compose.yaml
      vars.env               # Non-secret DNS config (upstream resolvers, etc.)
      .env                   # gitignored: WEBPASSWORD, FTLCONF_* secrets
    nebula-sync/
      compose.yaml
      vars.env               # Sync interval, source/destination labels
      .env                   # gitignored: API tokens for both PiHole instances
    uptime-kuma/
      compose.yaml
      vars.env
```

**Why a top-level `pi/` rather than merging into `services/`:**
The Pi is a separate host. Mixing its stacks into `services/` would imply they run on
the NAS. Keeping `pi/` distinct makes the host boundary explicit and allows `global.env`
to hold Pi-specific values (different PUID/PGID if needed, different TZ base path, etc.).

**Action required from user:**
Share the contents of the existing compose file(s) on the Pi so they can be
reverse-engineered into the `pi/services/` structure with correct image pins and
env separation. Run on the Pi:

```bash
cat ~/path/to/compose.yaml     # or wherever it lives
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

**Deliverables:**
- `pi/README.md`
- `pi/global.env`
- `pi/services/pihole/compose.yaml` + `vars.env`
- `pi/services/nebula-sync/compose.yaml` + `vars.env`
- `pi/services/uptime-kuma/compose.yaml` + `vars.env`
- Update root `README.md` to reference `pi/` directory
- Update `ARCHITECTURE.md` to document the Pi host (IP, role, access method)

**Rollback:** Purely additive — no running service is touched. Safe to abandon at any point.

---

### 08.3 — OS Security Hardening

**Goal:** Harden the Pi OS to a reasonable baseline for a LAN-only host.

**SSH hardening** (`/etc/ssh/sshd_config`):

```
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
```

> **Critical:** Verify key-based login works in the CURRENT session before restarting sshd.
> Test with a second terminal: `ssh pi@<pi-ip>` must succeed. Only then restart sshd.

**ufw rules** (order matters — add allow rules BEFORE enabling):

```bash
sudo ufw allow 22/tcp          # SSH
sudo ufw allow 53/tcp          # DNS (TCP)
sudo ufw allow 53/udp          # DNS (UDP) — critical for PiHole LAN clients
sudo ufw allow 80/tcp          # PiHole web UI
sudo ufw allow 3001/tcp        # UptimeKuma
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

**fail2ban** (SSH jail only):

```bash
sudo apt install fail2ban
```

Default config covers SSH. No custom jail needed beyond verifying `[sshd]` is enabled
in `/etc/fail2ban/jail.local`.

**User audit:**

- Confirm the `pi` user does not have the default `raspberry` password:
  `passwd pi` — set a strong password or confirm it was already changed.
- Confirm no other default accounts with known passwords exist.

**Rollback:**
- SSH: revert `sshd_config`, `sudo systemctl restart ssh`
- ufw: `sudo ufw disable`
- fail2ban: `sudo systemctl stop fail2ban`

---

### 08.4 — OS Auto-Updates (unattended-upgrades)

**Goal:** Security patches applied automatically. No surprise reboots.

**Install and configure:**

```bash
sudo apt install unattended-upgrades apt-listchanges
sudo dpkg-reconfigure --priority=low unattended-upgrades
```

**`/etc/apt/apt.conf.d/50unattended-upgrades` key settings:**

```
Unattended-Upgrade::Origins-Pattern {
    "origin=Debian,codename=${distro_codename},label=Debian-Security";
    "origin=Raspbian,codename=${distro_codename},label=Raspbian";
};
Unattended-Upgrade::Automatic-Reboot "false";          // MUST be false
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Mail "root";
```

**`/etc/apt/apt.conf.d/20auto-upgrades`:**

```
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
```

**Why no auto-reboot:** PiHole is the backup DNS resolver for the LAN. A surprise
reboot during the night is low-risk (primary NAS PiHole would handle DNS), but
UptimeKuma running on the same host would also go offline — creating false-positive
alerts for unrelated services. Manual reboots on kernel updates are the safer posture.

**Verify with:**

```bash
sudo unattended-upgrade --dry-run --debug
```

**Rollback:** `sudo apt remove unattended-upgrades`

---

### 08.5 — Docker Auto-Update via Cron

**Goal:** Keep Pi containers up to date automatically. No notifications needed — UptimeKuma
monitors PiHole health, and the NAS PiHole is the primary DNS so a brief restart is safe.

**Image tag strategy:**

| Service | Tag | Reason |
|---------|-----|--------|
| `pihole` | `:latest` | Backup DNS only; NAS PiHole covers any downtime during restart |
| `nebula-sync` | `:latest` | Small utility with no major-version float tag |
| `uptime-kuma` | `:2` | Major-version float; keeps monitor stable within v2.x |

**Update mechanism:** A cron script at `pi/scripts/update-containers.sh` runs nightly,
pulls new images for all stacks, and restarts any that changed.

**Setup on Pi:**

```bash
# Make script executable
chmod +x /home/grimur/homelab/pi/scripts/update-containers.sh

# Add to crontab (crontab -e)
0 3 * * 3 /home/grimur/homelab/pi/scripts/update-containers.sh >> /var/log/container-updates.log 2>&1
```

**UptimeKuma monitor:** Add an HTTP monitor for `http://localhost/admin` (PiHole web UI)
or a DNS monitor on `localhost:53` so any post-update failure is caught immediately.

**Rollback:** Remove the crontab entry. Revert image tags to pinned versions in compose files
and run `docker compose up -d` to re-deploy from the pinned image.

---

## Risk Summary

| # | Sub-milestone | Key risk | Mitigation |
|---|---------------|----------|------------|
| 08.2 | Repo documentation | Mis-documenting live config | Verify against `docker inspect` / running compose |
| 08.3 | SSH hardening | Lockout if key not confirmed first | Test key login before restarting sshd |
| 08.3 | ufw | Blocking UDP 53 takes down LAN DNS | Add 53/udp rule explicitly before enabling ufw |
| 08.4 | unattended-upgrades | Auto-reboot setting | Explicitly set `Automatic-Reboot "false"` |
| 08.5 | WUD socket | Unnecessary write access | Mount docker.sock as `:ro` |

---

## Blind Spot: UptimeKuma Monitoring Itself

UptimeKuma runs on the Pi. If the Pi goes down (bad update, hardware fault), the monitor
that should alert you is also down. This is a known architectural limitation — acceptable
for a homelab but worth documenting. A future mitigation would be a second UptimeKuma
instance on the NAS monitoring the Pi's services, or a dead-man's switch external check.

---

## Execution Order

1. **08.1** ✅ — repo published.
2. **08.2** — get the services documented before touching anything operational.
3. **08.3** — harden while services are stable and known.
4. **08.4** — add auto-patching once the baseline is confirmed clean.
5. **08.5** — add auto-updates last (lowest priority, purely additive).

---

## Open Questions

1. What is the Pi's current hostname and LAN IP? Needed for `pi/global.env` and `ARCHITECTURE.md`.
2. Where does the existing compose file live on the Pi? (`~/` or a dedicated dir?)
3. Does Nebula-Sync authenticate to the NAS PiHole using the admin password, or a dedicated API token? (Affects what goes in `.env`.)
4. Is the Pi on a static IP or DHCP reservation?
