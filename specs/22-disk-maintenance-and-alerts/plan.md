# Spec 22: Docker Log Rotation, Weekly Image Pruning & Beszel Disk Alerting

## 📌 Context & Problem

The primary NAS uses a 256GB OS drive. While 256GB is more than adequate for the OS and Docker container configurations/databases, unmanaged Docker environments suffer from three common failure modes that consume disk space unexpectedly:
1. **Unbounded Container Logs:** Docker's default `json-file` logging driver has no file size limit. A chatty or error-looping container can write tens of gigabytes to `/var/lib/docker/containers/`.
2. **Dangling & Unused Image Accumulation:** Updating containers (e.g., via Watchtower/WUD or manual compose pulls) leaves behind superseded image layers in `/var/lib/docker/overlay2/`.
3. **Lack of Early Warning:** Without proactive disk usage alerting, space exhaustion is only noticed when services crash or database writes fail.

---

## 🎯 Objectives

1. **Global Docker Log Rotation:** Enforce maximum log size and file count across all Docker containers on both the NAS (`192.168.86.17`) and Raspberry Pi (`192.168.86.26`).
2. **Automated Weekly Docker Prune:** Deploy a systemd timer or cron job to safely remove unused images older than 7 days (`168h`) and build cache without impacting running services or volumes.
3. **Beszel Disk Usage Alerts:** Configure Beszel Hub (`monitoring.internal.pippinn.me`) to alert when root disk (`/`) usage crosses 80%.

---

## 🛠️ Implementation Plan

### Part 1: Global Docker Log Rotation

Set global logging defaults in `/etc/docker/daemon.json` on both NAS and Pi.

#### Target File: `/etc/docker/daemon.json`
```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "20m",
    "max-file": "3"
  }
}
```
*Note: If existing keys exist in `daemon.json`, merge the `log-driver` and `log-opts` keys.*

#### Application:
```bash
sudo systemctl reload docker # or sudo systemctl restart docker
```
*Existing running containers will adopt the new policy upon their next recreate (`docker compose up -d`).*

---

### Part 2: Weekly Docker Cleanup Job (systemd Timer)

Deploy a dedicated systemd service and timer to automatically prune unused images and build caches weekly.

#### 1. Service: `/etc/systemd/system/docker-prune.service`
```ini
[Unit]
Description=Prune unused Docker images and build cache
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker image prune -af --filter "until=168h"
ExecStartPost=/usr/bin/docker builder prune -af --filter "until=168h"
```

#### 2. Timer: `/etc/systemd/system/docker-prune.timer`
```ini
[Unit]
Description=Weekly Docker Prune Timer

[Timer]
OnCalendar=Sun *-*-* 03:30:00
Persistent=true
RandomizedDelaySec=1800

[Install]
WantedBy=timers.target
```

#### 3. Enable & Start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now docker-prune.timer
```

*Why `docker image prune -af --filter "until=168h"`?*
- `-a`: Removes unused images, not just dangling ones (cleans up superseded versions of pulled images).
- `--filter "until=168h"`: Protects recently pulled images or rollback candidates (keeps anything pulled within 7 days).
- **Safe for volumes**: Does **not** touch named volumes or database state.

---

### Part 3: Beszel Disk Usage Alerting

Beszel Hub runs on the Raspberry Pi (`http://192.168.86.26:8090` / `https://monitoring.internal.pippinn.me`) with Beszel Agent running on both the NAS and Pi.

#### Configuration Steps:
1. Log into Beszel Hub web interface.
2. Navigate to **System Settings / Alerts** for each managed system (**NAS** & **Raspberry Pi**).
3. Set **Disk Usage Alert**:
   - **Filesystem / Mount Point:** `/` (Root partition)
   - **Warning Threshold:** `80%`
   - **Critical Threshold:** `90%`
4. Verify notification channel (Discord webhook, Telegram, or Email) is active in Beszel.

---

## ✅ Verification Checklist

- [ ] Check Docker daemon log config: `docker info --format '{{json .LoggingDriver}}'` returns `"json-file"`.
- [ ] Inspect a newly started container: `docker inspect <container_id> --format '{{json .HostConfig.LogConfig}}'` shows `max-size=20m` and `max-file=3`.
- [ ] Verify systemd timer status: `systemctl list-timers docker-prune.timer`.
- [ ] Test-run the prune service: `sudo systemctl start docker-prune.service && journalctl -u docker-prune.service -n 20`.
- [ ] Verify Beszel Hub displays alert threshold indicators on the `/` disk meter.

