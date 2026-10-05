# Milestone 24: Connecting Dozzle to Raspberry Pi — Summary

## 📌 What Was Changed

1. **Pi Hardened Dozzle Stack (`pi/services/dozzle-agent/compose.yaml`):**
   - Deployed `wollomatic/socket-proxy:1` sidecar:
     - Bound to `/var/run/docker.sock:ro` with `no-new-privileges:true`.
     - Non-root user: `65534:985` matching Raspberry Pi OS Bookworm `docker` group GID `985`.
     - Restricted to private internal network `socket_proxy`.
     - Granular API allowlists: GET for container inspect, stats, logs, system df, images; HEAD for ping; POST regex limited strictly to container `start`, `stop`, `restart`.
   - Deployed `amir20/dozzle:latest` in agent mode:
     - Communicates with Docker daemon exclusively via `DOCKER_HOST: tcp://socket-proxy:2375`.
     - Exposes port `7007:7007` to LAN with built-in TLS encryption.
     - Tagged host as `pihole-pi`.
     - Resource capped at `0.25` CPU / `64M` RAM; JSON logging capped at `10m/3`.

2. **NAS Dozzle Service (`services/dozzle/compose.yaml`):**
   - Added `DOZZLE_REMOTE_AGENT: 192.168.86.26:7007` to environment.

3. **Automation & Documentation:**
   - [`pi/scripts/update-containers.sh`](file:///Users/grimur/personal-code/homelab/pi/scripts/update-containers.sh): Added `dozzle-agent` to `STACKS` array for weekly cron updates.
   - [`pi/README.md`](file:///Users/grimur/personal-code/homelab/pi/README.md): Documented Dozzle agent service and directory layout.
   - [`QUIRKS.md`](file:///Users/grimur/personal-code/homelab/QUIRKS.md): Added Q8 documenting Docker GID differences across hosts (NAS: `995`, Pi: `985`).
   - [`ARCHITECTURE.md`](file:///Users/grimur/personal-code/homelab/ARCHITECTURE.md): Updated Dozzle entry to reflect multi-host monitoring of `pihole-pi`.

---

## 🎯 Why It Was Changed

- **Centralized Visibility:** Consolidated real-time container log streaming and lifecycle monitoring across both the primary NAS and auxiliary Raspberry Pi into a single Authelia-protected web UI (`https://logs.internal.pippinn.me`).
- **Security Hardening:** Avoided mounting the raw Docker socket directly to Dozzle agent by deploying `socket-proxy`. This isolates Docker API access to container inspection and start/stop/restart actions while completely preventing destructive actions (e.g. container creation, deletion, or exec).

---

## 🔑 New Secrets & Environment Variables

- **New Secrets:** None.
- **New Environment Variables:** None requiring `.env`. Static non-secret configurations (`DOZZLE_REMOTE_AGENT: 192.168.86.26:7007` and `DOZZLE_HOSTNAME: pihole-pi`) were set directly in compose files per repository conventions.

---

## 📋 Architecture & Global Env Status

- **`ARCHITECTURE.md`:** Updated (Dozzle multi-host entry added under Hosts section).
- **`global.env` / `pi/global.env`:** No update needed.
