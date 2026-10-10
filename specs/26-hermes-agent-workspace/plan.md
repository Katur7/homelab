# Milestone 26: Hermes AI Agent & Workspace Deployment

## 📌 Context & Objectives

To enable autonomous AI-assisted operations in the homelab while maintaining strict infrastructure stability and security, we are deploying:
1. **Hermes Agent (Host Daemon):** An open-source autonomous agent (Nous Research) running natively on the Debian NAS (`pippinn`) under the `grimur` user. Running on the host grants it direct access to the `homelab` repository, `git`, and the Docker CLI to test and deploy workloads without complex Docker-in-Docker translation layers.
2. **Tirith Security & Smart Approvals:** Configured in `smart` approval mode to auto-approve harmless read-only inspections (`cat`, `ls`, `git status`, `docker ps`), while enforcing interactive user confirmations for destructive or high-risk actions (file edits, deletes, resets, container recreation).
3. **Hermes Workspace (Web UI):** A browser-based management dashboard (`ghcr.io/outsourc-e/hermes-workspace`) containerized in `services/hermes/compose.yaml`, routed through Traefik v3 with Authelia authentication at `https://hermes.internal.pippinn.me`.
4. **Milestone Handover:** Once verified, Hermes will be tasked with executing **Milestone 27: Laya Local AI Stack** (`specs/27-laya-local-ai/`).

---

## 🛠️ Architecture & Decisions

### 1. Host Daemon Setup (NAS `pippinn`)
- **Runtime User:** `grimur`
- **Installation:** Isolated environment via `pipx` or virtualenv (`~/.local/share/hermes/venv`) with `hermes-agent`.
- **Systemd Service:** `~/.config/systemd/user/hermes.service` (or `/etc/systemd/system/hermes.service`) running `hermes gateway run`. User lingering enabled via `loginctl enable-linger grimur` to ensure persistence across sessions.
- **Port & Binding:** Gateway API listens on port `8642` (`0.0.0.0:8642` or `172.17.0.1:8642` for Docker bridge access).
- **Credentials & Environment (`~/.hermes/.env`):**
  - Stored outside git repository in the user's home directory.
  - Contains `GEMINI_API_KEY`.
- **Configuration (`~/.hermes/config.yaml`):**
  - Model: Google Gemini (`gemini-3.8-flash` or `gemini-2.5-pro`).
  - Terminal Backend: `local` (executes directly on host with access to `/home/grimur/personal-code/homelab` and `docker`).
  - Security / Approvals:
    ```yaml
    security:
      tirith_enabled: true
    approvals:
      mode: smart
      timeout: 300
    ```

### 2. Hermes Workspace Service (`services/hermes/compose.yaml`)
- **Image:** `ghcr.io/outsourc-e/hermes-workspace:latest`
- **Networks:** `traefik_internal`
- **Backend Connection:** `HERMES_AGENT_URL=http://host.docker.internal:8642`
- **Traefik Ingress:**
  - Entrypoint: `websecure` (internal LAN only via global allowlist).
  - Rule: `Host(`hermes.internal.pippinn.me`)`
  - Middleware: `authelia-auth@file`
- **Resource Limits:**
  - CPU: `0.5`
  - Memory: `256M`
- **Restart Policy:** `unless-stopped`

### 3. DNS Configuration
- Register `hermes` on PiHole DNS via `./scripts/add-dns.sh hermes` (maps `hermes.pippinn.me` and `hermes.internal.pippinn.me` to NAS IP `192.168.86.17`).

---

## 📋 Execution Steps

### Step 1: Create Host Setup Script & Systemd Unit
1. Create `scripts/setup/hermes/setup.sh` to automate:
   - Python virtualenv creation for Hermes Agent.
   - Initial configuration generation (`~/.hermes/config.yaml` with Tirith `smart` approvals).
   - Systemd unit installation (`hermes.service`) and user lingering.
2. Create `scripts/setup/hermes/hermes.service`.

### Step 2: Create Docker Compose Stack for Hermes Workspace
1. Create `services/hermes/compose.yaml`.
2. Create `services/hermes/vars.env` and `services/hermes/.env.example`.
3. Add `services/hermes/data/` to `.gitignore` (if applicable for mutable workspace storage).

### Step 3: Configure DNS & Traefik Routing
1. Run `./scripts/add-dns.sh hermes` to register DNS records in PiHole.
2. Validate compose syntax:
   ```bash
   docker compose -f services/hermes/compose.yaml config
   ```

### Step 4: Verification & Approval Testing
1. Verify systemd daemon status: `systemctl --user status hermes.service`.
2. Launch workspace stack: `docker compose -f services/hermes/compose.yaml up -d`.
3. Verify access at `https://hermes.internal.pippinn.me` through Authelia SSO.
4. Verify connection between Workspace UI and host Agent Gateway.
5. Trigger test actions in Workspace:
   - Test read-only command (e.g. `git status`): verify auto-approved.
   - Test write/destructive command: verify approval prompt displayed in UI.

---

## 🔄 Rollback Steps

If any issues arise during deployment:
1. Stop and remove the workspace container:
   ```bash
   docker compose -f services/hermes/compose.yaml down -v
   ```
2. Stop and disable the host systemd service:
   ```bash
   systemctl --user stop hermes.service
   systemctl --user disable hermes.service
   ```
3. Remove DNS records from PiHole if necessary.
