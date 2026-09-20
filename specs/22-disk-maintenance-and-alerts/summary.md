# Spec 22: Docker Log Rotation, Weekly Image Pruning & Beszel Disk Alerting — Summary

## What Was Created

1. **Systemd Prune Service & Timer:**
   - [`scripts/docker-prune.service`](file:///Users/grimur/personal-code/homelab/scripts/docker-prune.service): Runs `docker image prune -af --filter "until=168h"` and `docker builder prune -af --filter "until=168h"` without deleting named data volumes.
   - [`scripts/docker-prune.timer`](file:///Users/grimur/personal-code/homelab/scripts/docker-prune.timer): Schedules the service to run every Sunday at 03:30 (with randomized delay).

2. **Automated Setup Script:**
   - [`scripts/setup-docker-maintenance.sh`](file:///Users/grimur/personal-code/homelab/scripts/setup-docker-maintenance.sh):
     - Safely merges global log rotation (`max-size: 20m`, `max-file: 3`) into `/etc/docker/daemon.json`.
     - Reloads the Docker daemon.
     - Copies and enables the systemd service and timer.

3. **Beszel Hub Disk Space Alerting:**
   - Configured in Beszel Hub (`https://monitoring.internal.pippinn.me` / `http://192.168.86.26:8090`) on the root (`/`) filesystem for both NAS and Pi hosts:
     - Warning threshold: **80%**
     - Critical threshold: **90%**

---

## Deployment Instructions

### On NAS (`192.168.86.17`) and Pi (`192.168.86.26`)

Run the setup script:
```bash
sudo /home/grimur/homelab/scripts/setup-docker-maintenance.sh
```

### In Beszel Hub UI
1. Open `https://monitoring.internal.pippinn.me`
2. Under Systems → Select **NAS** / **Raspberry Pi** → Alerts
3. Add/update Disk Alert for `/`:
   - **Warning:** `80%`
   - **Critical:** `90%`

