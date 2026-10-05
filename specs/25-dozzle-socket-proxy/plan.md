# Milestone 25: Docker Socket Proxy for NAS Dozzle

## 📌 Context & Objectives

In homelab infrastructure, granting containers direct access to `/var/run/docker.sock` provides root-equivalent control over the host Docker daemon.

Following an audit of Docker socket mounts across the repository:
- **Infrastructure Gateway (`infrastructure/gateway`):** Runs `wollomatic/socket-proxy:1`, serving filtered Docker API access to Traefik, Sablier, and WUD.
- **Raspberry Pi Dozzle Agent (`pi/services/dozzle-agent`):** Hardened in Milestone 24 to communicate exclusively via a local `socket-proxy` sidecar (`DOCKER_HOST: tcp://socket-proxy:2375`).
- **Beszel Agent (NAS & Pi):** Runs in `network_mode: host` with device access (`SYS_RAWIO`), mounting the socket read-only for metrics.
- **WUD Autoupdater (NAS):** Needs full Docker CLI orchestration (`pull`, `build`, `tag`, `compose up`) to self-update stacks, isolated on internal `wud_internal`.
- **Dozzle (NAS, `services/dozzle`):** Currently mounts `/var/run/docker.sock` directly with read-write permissions.

**Goal:** Migrate NAS Dozzle from a raw Docker socket mount to the existing gateway `socket-proxy`. This isolates Docker API access to read operations and container lifecycle commands (`start`, `stop`, `restart`), completely blocking container creation, deletion, exec, and volume/privilege escalation from Dozzle.

---

## 🛠️ Architecture & Decisions

1. **Gateway Socket Proxy Rules Update (`infrastructure/gateway/compose.yaml`):**
   - **`SP_ALLOW_GET`:** Add `info` and `_ping` to support Dozzle host telemetry and health checks:
     ```yaml
     - SP_ALLOW_GET=(/v1\..{1,2})?/(version|info|_ping|containers/.*|networks|nodes|services|system/df|events.*|images/.*)
     ```
   - **`SP_ALLOW_POST`:** Generalize start/stop/restart for containers to support Dozzle's UI action buttons (`DOZZLE_ENABLE_ACTIONS: "true"`) alongside Sablier:
     ```yaml
     - SP_ALLOW_POST=(/v1\..{1,2})?/containers/([a-zA-Z0-9_.-]+)/(start|stop|restart)
     ```
     This allows container lifecycle control while strictly blocking dangerous endpoints (`POST /containers/create`, `DELETE /containers/...`, `POST /containers/.../exec`, etc.).

2. **Dozzle Stack Configuration (`services/dozzle/compose.yaml`):**
   - Remove `/var/run/docker.sock:/var/run/docker.sock` volume mount.
   - Join external network `socket_proxy`.
   - Set environment variables:
     ```yaml
     DOCKER_HOST: tcp://socket-proxy:2375
     DOZZLE_HOSTNAME: pippinn
     ```
   - Declare `socket_proxy` network with `external: true`.

3. **Documentation:**
   - Update `ARCHITECTURE.md` to document the socket proxy integration for Dozzle.

---

## 📋 Execution Steps

### Step 1: Update Gateway Socket Proxy (`infrastructure/gateway/compose.yaml`)
Update `SP_ALLOW_GET` and `SP_ALLOW_POST` environment variables.

### Step 2: Update NAS Dozzle Stack (`services/dozzle/compose.yaml`)
Remove direct Docker socket volume mount, add `socket_proxy` network attachment, and set `DOCKER_HOST` & `DOZZLE_HOSTNAME`.

### Step 3: Update `ARCHITECTURE.md`
Record the hardened socket architecture.

### Step 4: Verification & Testing
1. Validate compose syntax:
   ```bash
   docker compose -f infrastructure/gateway/compose.yaml config
   docker compose -f services/dozzle/compose.yaml config
   ```
2. Restart gateway stack (to apply updated socket-proxy rules):
   ```bash
   cd ~/homelab/infrastructure/gateway && docker compose up -d socket-proxy
   ```
3. Restart Dozzle stack:
   ```bash
   cd ~/homelab/services/dozzle && docker compose up -d --force-recreate
   ```
4. Verify:
   - Access `https://logs.internal.pippinn.me`.
   - Confirm host `pippinn` containers and logs stream properly without socket permission errors.
   - Confirm multi-host view (`pippinn` and `pihole-pi`) remains intact.
   - Test restarting or stopping a test container from Dozzle.

---

## ↩️ Rollback Plan
- Revert `services/dozzle/compose.yaml` to mount `/var/run/docker.sock:/var/run/docker.sock` and remove `DOCKER_HOST` & `socket_proxy`.
- Revert `infrastructure/gateway/compose.yaml` if needed.
- Run `docker compose up -d` in both directories.
