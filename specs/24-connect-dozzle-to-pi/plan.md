# Milestone 24: Connecting Dozzle to Raspberry Pi (Multi-Host Monitoring)

## 📌 Context & Objectives

Milestone 17 established Dozzle on the primary NAS (`pippinn`, `192.168.86.17`) behind Authelia at `https://logs.internal.pippinn.me` for real-time container log viewing and lifecycle control (`DOZZLE_ENABLE_ACTIONS: "true"`).

The Raspberry Pi (`192.168.86.26`) runs auxiliary services (PiHole DNS, Nebula-Sync, UptimeKuma, Photoframe, Beszel agent, and Immich ML). Currently, monitoring Pi container logs and health requires direct SSH access.

**Goal:** Connect the primary NAS Dozzle instance to a Dozzle agent running on the Raspberry Pi so all homelab container logs and lifecycle actions across both hosts can be viewed and managed from a unified dashboard at `https://logs.internal.pippinn.me`.

---

## 🛠️ Architecture & Decisions

1. **Hardened Agent Deployment on Pi (`pi/services/dozzle-agent/compose.yaml`):**
   - **Socket Proxy (`wollomatic/socket-proxy:1`):**
     - Mounts `/var/run/docker.sock:/var/run/docker.sock:ro` (read-only)
     - Security: `no-new-privileges:true`, running as `user: "65534:985"` (Pi Docker GID: 985)
     - Isolated on private internal network `socket_proxy` (`internal: true`)
     - Read endpoints: `SP_ALLOW_GET=(/v1\..{1,2})?/(version|info|_ping|containers/.*|events.*|system/df|images/.*)` and `SP_ALLOW_HEAD=/_ping`
     - Action endpoints: `SP_ALLOW_POST=(/v1\..{1,2})?/containers/([a-zA-Z0-9_.-]+)/(start|stop|restart)` (allows start/stop/restart only, blocks destructive API calls)
     - Resource limits: `0.1` CPU, `32M` memory
   - **Dozzle Agent (`amir20/dozzle:latest`):**
     - Runs with `command: agent`
     - Connects exclusively via `DOCKER_HOST: tcp://socket-proxy:2375` (no direct socket mount)
     - Hostname tag: `DOZZLE_HOSTNAME: pihole-pi`
     - Port: Exposes `7007:7007` on the LAN with built-in TLS
     - Resource limits: `0.25` CPU, `64M` memory
     - Logging: `json-file` with `max-size: 10m` and `max-file: 3`

2. **Primary NAS Configuration:**
   - Modify `services/dozzle/compose.yaml` to include:
     ```yaml
     DOZZLE_REMOTE_AGENT: 192.168.86.26:7007
     ```
   - Retains existing Authelia proxy authentication and `traefik_internal` routing.

3. **Automation & Maintenance:**
   - Include `dozzle-agent` in `pi/scripts/update-containers.sh` under `STACKS` array so weekly cron pulls and restarts the agent.
   - Update `pi/README.md` and `ARCHITECTURE.md`.

---

## 📋 Execution Steps

### Step 1: Create Pi Dozzle Agent Stack (`pi/services/dozzle-agent/compose.yaml`)
Create service definition with resource limits and logging parameters.

### Step 2: Update NAS Dozzle Configuration (`services/dozzle/compose.yaml`)
Add `DOZZLE_REMOTE_AGENT: 192.168.86.26:7007` to Dozzle container environment.

### Step 3: Update Pi Maintenance Script & Docs
- Add `dozzle-agent` to `STACKS` in `pi/scripts/update-containers.sh`.
- Update `pi/README.md` and `ARCHITECTURE.md`.

### Step 4: Verification & Deployment
- Validate compose configurations syntax (`docker compose config`).
- Deploy on Pi:
  ```bash
  cd ~/homelab/pi/services/dozzle-agent && docker compose up -d
  ```
- Deploy on NAS:
  ```bash
  cd ~/homelab/services/dozzle && docker compose up -d
  ```
- Verify: Access `https://logs.internal.pippinn.me`, confirm the host switcher shows both `pippinn` (local) and `pihole-pi` (agent), and verify log streaming and container actions on a Pi container (e.g. UptimeKuma/PiHole).

---

## ↩️ Rollback Plan
- To disconnect: Remove `DOZZLE_REMOTE_AGENT` from `services/dozzle/compose.yaml` on NAS and run `docker compose up -d`.
- To remove agent from Pi: Run `docker compose down` in `pi/services/dozzle-agent/` and revert `update-containers.sh`.
