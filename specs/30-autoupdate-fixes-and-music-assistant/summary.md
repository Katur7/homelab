# Milestone 30 Summary: Autoupdater Socket Permission Fix & Music Assistant Autoupdate

## 🎯 What Was Done

1. **Fixed Autoupdater Socket Permissions:**
   - Updated `user: "1000:992"` to `user: "1000:995"` in [`infrastructure/wud/compose.yaml`](file:///home/grimur/homelab/infrastructure/wud/compose.yaml) to match the host `docker` group GID (`995`).
   - Resolved `permission denied` connecting to `/var/run/docker.sock` that was causing all autoupdate webhook events to fail silently.

2. **Hardened Tag In-Place Replacement Logic:**
   - Modified [`infrastructure/wud/updater.py`](file:///home/grimur/homelab/infrastructure/wud/updater.py) to scope tag replacements (`update_compose_tag` and `revert_compose_tag`) specifically within the targeted service's compose definition block instead of an unconstrained file-wide single replacement. This prevents short/floating tags (e.g. `2`) from corrupting earlier lines or year-based version tags (e.g. `2026.10.4`).
   - Rebuilt `autoupdater:local` container image and restarted the service.

3. **Enabled Autoupdate for Music Assistant:**
   - Added `"wud.autoupdate=true"` label to `music-assistant-server` in [`services/home-assistant/compose.yaml`](file:///home/grimur/homelab/services/home-assistant/compose.yaml).
   - Successfully processed the pending update: `music-assistant-server` was updated from tag `2` to `2.10.9`, verified healthy, and committed autonomously.

---

## 💡 Why It Was Done

- Host docker group was GID 995, leaving the non-root container user unable to communicate with the Docker daemon.
- Music Assistant was requested to be managed autonomously by the WUD updater alongside other media applications.
- Service scoping in regex replacement ensures safe upgrades when multiple services reside within a single compose file.

---

## 🔑 New Secrets & Variables Created

None.

---

## 📋 Architecture & Environment Impacts

- **`global.env`:** No updates required.
- **`ARCHITECTURE.md`:** No updates required.
