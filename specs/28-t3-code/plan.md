# Milestone 28: T3 Code Agent Harness & Control Surface Deployment

## 📌 Context & Objectives

To enable multi-agent supervision, Git worktree isolation, and GUI-driven orchestration of AI coding agents (specifically Google Antigravity `agy`) within the homelab:
1. **T3 Code Host Daemon:** Installed using the official T3 install script and managed using T3's built-in service installer (`t3 service install`) running natively on Debian NAS (`pippinn`) under the `grimur` user.
2. **Access & Security:** Bound to `172.17.0.1:3773` (Docker bridge interface), preventing direct LAN port exposure.
3. **Ingress & SSO:** Ingress exclusively via Traefik v3 dynamic router at `https://t3.internal.pippinn.me` (no public `t3.pippinn.me` domain).
4. **Strict Authentication:** Strictly gated by Authelia (`authelia-auth` middleware + Authelia `two_factor` policy) and LAN allowlist (`internal-only`). Unauthenticated requests are redirected to Authelia SSO login.
5. **DNS Resolution:** Registered in Pi-hole DNS strictly for `t3.internal.pippinn.me`.
6. **Workspace Management:** Accessible root `/home/grimur`, enabling supervision of `/home/grimur/homelab` and other host repositories with Git worktree isolation.
7. **Agent Integration:** Antigravity CLI (`agy`) integration via host environment.
8. **Phased Roadmap:**
   - **Phase 1 (This Milestone):** T3 Code host deployment, systemd service, Traefik v3 routing, Authelia SSO enforcement, and Antigravity verification.
   - **Phase 2 (Follow-up Sub-milestone):** Docker Sandboxes (`sbx` / SSH containers) for isolated non-homelab coding projects.

---

## 🛠️ Architecture & Decisions

### 1. Host Daemon Setup (NAS `pippinn`)
- **Runtime User:** `grimur`
- **Installation:** Official T3 install script:
  ```bash
  curl -fsSL https://t3.codes/install.sh | sh
  ```
- **Service Registration:** Built-in T3 service tool:
  ```bash
  t3 service install --host 172.17.0.1 --port 3773
  ```
  *(or verify installed systemd service unit binds to `172.17.0.1:3773`)*
- **Session Persistence:** `loginctl enable-linger grimur` to keep the user service alive across sessions and reboots.
- **Environment:** Inherits user `PATH` containing `~/.local/bin` (where `agy` and `t3` reside).

### 2. Authelia Access Control (`infrastructure/gateway/config/authelia/configuration.yml`)
- Add rule for `*.internal.pippinn.me` or `t3.internal.pippinn.me` requiring authentication:
  ```yaml
  - domain: 't3.internal.pippinn.me'
    policy: two_factor
  ```
- Ensures requests arriving at Traefik trigger the Authelia login flow and are denied if unauthenticated.

### 3. Traefik Routing Configuration (`infrastructure/gateway/config/dynamic/routes.yml`)
- **Router:**
  - Name: `t3`
  - EntryPoints: `websecure`
  - Rule: `Host(`t3.internal.pippinn.me`)`
  - Middlewares:
    - `internal-only@file`
    - `authelia-auth@file`
  - Service: `t3`
- **Service:**
  - Name: `t3`
  - URL: `http://172.17.0.1:3773`
  - `passHostHeader: true`

### 4. DNS Configuration
- Pi-hole local DNS record registered strictly for `t3.internal.pippinn.me` pointing to NAS IP `192.168.86.17`:
  ```bash
  ./scripts/add-dns.sh t3.internal
  ```
- No record created for `t3.pippinn.me`.

---

## 📋 Execution Steps

### Step 1: Install T3 Code & Configure Host Service
1. Run official installer:
   ```bash
   curl -fsSL https://t3.codes/install.sh | sh
   ```
2. Verify binary installed in `~/.local/bin/t3` and check options for `t3 service install`:
   ```bash
   t3 --help
   t3 service --help
   ```
3. Register service using built-in command:
   ```bash
   t3 service install --host 172.17.0.1 --port 3773
   ```
4. Enable linger:
   ```bash
   loginctl enable-linger grimur
   ```
5. Start/verify systemd service status:
   ```bash
   systemctl --user status t3.service
   ```

### Step 2: Configure Authelia & Register DNS
1. Add `t3.internal.pippinn.me` with `policy: two_factor` to `infrastructure/gateway/config/authelia/configuration.yml`.
2. Reload/restart Authelia container to load new configuration.
3. Run `./scripts/add-dns.sh t3.internal` to register `t3.internal.pippinn.me` on Pi-hole.

### Step 3: Configure Traefik Dynamic Routes
1. Add `t3` router and service to `infrastructure/gateway/config/dynamic/routes.yml`.
2. Verify Traefik picks up dynamic configuration without errors in access/service logs.

### Step 4: Verification & Operational Testing
1. Test direct local bind:
   ```bash
   curl -I http://172.17.0.1:3773
   ```
2. Test unauthenticated external access from LAN:
   ```bash
   curl -I https://t3.internal.pippinn.me
   ```
   Verify it returns HTTP 302 redirecting to `https://auth.pippinn.me`.
3. Open `https://t3.internal.pippinn.me` in browser, authenticate through Authelia, and verify T3 Code dashboard loads.
4. Verify Antigravity (`agy`) is discovered and ready for tasks.

---

## 🔮 Phase 2: Docker Sandboxes (Follow-up Sub-milestone)

Once Phase 1 is verified:
1. **Target:** Sandbox execution for third-party/external repositories without granting full host filesystem access.
2. **Mechanism:** Leverage T3 Code's native SSH connection provider to target Docker containers running SSH daemon or Docker Sandboxes CLI (`sbx`).
3. **Isolation:** Containerized runtime with agent CLI binaries, isolated git workspace mounts, and locked network policies.

---

## 🔄 Rollback Steps

If any issues occur during deployment:
1. **Stop & Remove Built-in Service:**
   ```bash
   t3 service uninstall || (systemctl --user stop t3.service && systemctl --user disable t3.service)
   ```
2. **Revert Traefik Dynamic Configuration:**
   Remove `t3` router and service blocks from `infrastructure/gateway/config/dynamic/routes.yml`.
3. **Revert Authelia Configuration:**
   Remove `t3.internal.pippinn.me` rule from `infrastructure/gateway/config/authelia/configuration.yml`.
4. **Remove DNS Record:**
   Remove `t3.internal.pippinn.me` from Pi-hole custom DNS.
5. **Remove Binary:**
   Remove `~/.local/bin/t3`.
