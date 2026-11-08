# Milestone 28: T3 Code Agent Harness & Control Surface Deployment — Summary

## 📌 Overview & Outcome
Successfully deployed **T3 Code** (`pingdotgg/t3code` v0.1.7) natively on the Debian NAS (`pippinn`) to supervise AI coding agents (Google Antigravity `agy`) with Git worktree isolation and approval workflows. Accessible securely at `https://t3.internal.pippinn.me`.

---

## 🛠️ What Was Changed & Why

1. **Host Daemon & Service Management:**
   - **Action:** Installed T3 Code using the official installer (`curl -fsSL https://t3.codes/install.sh | sh`) into `~/.local/bin/t3`.
   - **Service:** Registered systemd user service via `t3 service install`, managed at `~/.config/systemd/user/t3code.service`.
   - **Network Isolation:** Configured `~/.t3/service.env` with `T3CODE_HOST=172.17.0.1` and `T3CODE_PORT=3773` so the daemon binds strictly to the Docker bridge interface rather than exposing ports directly on the LAN.
   - **Persistence:** Confirmed `loginctl enable-linger grimur` so the user service survives logouts and system reboots.

2. **Node.js Runtime & Agent Environment:**
   - **Action:** Installed `fnm` (Fast Node Manager) to `~/.local/bin/fnm` and installed **Node v26.13.0 (LTS Lithium)**.
   - **Symlinks:** Created symlinks in `~/.local/bin` for `node`, `npm`, `npx`, `agy-ide`, and `antigravity-ide`.
   - **Service PATH:** Added `PATH=/home/grimur/.local/bin:/home/grimur/.local/share/fnm/aliases/default/bin:...` to `t3code.service` to resolve `NodeRuntimeUnavailableError` and allow ACP adapters and Antigravity detection.

3. **Ingress & Access Control:**
   - **Traefik Dynamic Routing (`infrastructure/gateway/config/dynamic/routes.yml`):** Defined router `t3` pointing to service `http://172.17.0.1:3773` protected by middlewares `internal-only@file` (LAN allowlist) and `authelia-auth@file` (Authelia forward-auth).
   - **Authelia Access Control (`infrastructure/gateway/config/authelia/configuration.yml`):** Added explicit `policy: two_factor` rule for `t3.internal.pippinn.me` so unauthenticated requests are redirected (HTTP 302) to `https://auth.pippinn.me`.
   - **DNS Registration:** Registered A and AAAA records strictly for `t3.internal.pippinn.me` in Pi-hole pointing to `192.168.86.17` via `./scripts/add-dns.sh t3.internal`.

4. **Architecture Documentation (`ARCHITECTURE.md`):**
   - Documented T3 Code host service under `## 🖥️ Hosts`.

---

## 🔑 Secrets & Variables

- **New Secrets:** None committed. T3 Code generates its own internal owner/session tokens in `~/.t3/userdata/secrets/` (outside the git repository).
- **Global Variables:** No changes to `global.env`.

---

## 🔮 Next Steps (Phase 2 Follow-up)

- **Docker Sandboxes:** Explore containerized SSH sandbox targets for non-homelab repositories where host filesystem isolation is desired.
