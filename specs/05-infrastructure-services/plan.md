# Milestone 05: Remaining Infrastructure Services — Plan

## Context
Three OMV-managed stacks remain in `/appdata/` that belong in `infrastructure/`:
- **WUD** (What's Up Docker) — container update monitor
- **Tailscale** — mesh VPN (kernel mode, pre-authenticated)
- **WireGuard** — road-warrior VPN (4 peers: Tryggvi, GrimurFlandri, GrimurPixel, GrimurMacFlandri)

All three follow the same migration pattern as Gateway, Cloudflare, and DNS milestones.

---

## Source Files

| Service | OMV compose | Key config |
|---------|------------|------------|
| WUD | `/appdata/whats-up-docker/whats-up-docker.yml` | No files — socket proxy only |
| Tailscale | `/appdata/tailscale/tailscale.yml` | `/appdata/tailscale/state/` (binary runtime state) |
| WireGuard | `/appdata/wireguard/wireguard.yml` | `/appdata/wireguard/config/` (server + peer keys) |

---

## Target Structure

```
infrastructure/
  wud/
    compose.yaml
    vars.env          ← WUD_REGISTRY_LSCR_USERNAME, WUD_WATCHER_*
    .env              ← WUD_REGISTRY_LSCR_PRIVATE_TOKEN (GitHub PAT)
  tailscale/
    compose.yaml
    vars.env          ← TS_STATE_DIR, TS_USERSPACE
    .env              ← TS_AUTHKEY
    state/            ← gitignored (binary runtime state)
  wireguard/
    compose.yaml
    vars.env          ← SERVERURL, SERVERPORT, PEERS, PEERDNS, LOG_CONFS
    config/           ← gitignored (server + peer private keys, auto-generated)
```

---

## 1. WUD (What's Up Docker)

**Image:** `getwud/wud:8.2.2` (pinned from running container)

**Changes from OMV:**
- Image pinned to `8.2.2`
- `${TRAEFIK_URL}` label variable replaced with hardcoded router name and hostname
- GitHub PAT (`WUD_REGISTRY_LSCR_PRIVATE_TOKEN`) moved to `.env`

**Networks:** `traefik_internal` + `socket_proxy` (external)

**Traefik:** `update.internal.pippinn.me` on `websecure` (internal-only)

---

## 2. Tailscale

**Image:** `tailscale/tailscale:stable` (rolling tag — acceptable, no versioned releases)

**Changes from OMV:**
- `TS_AUTHKEY` moved to `.env`
- State volume changed from `/appdata/tailscale/state/` → `./state/` (relative)

**Networks:** `traefik_internal` (no Traefik route — VPN only)

**Critical:** State must be copied before cutover. If state is missing, Tailscale
re-authenticates using `TS_AUTHKEY`. Auth keys may be one-time-use; if expired,
re-authentication will fail and a new key must be generated in the Tailscale admin console.

---

## 3. WireGuard

**Image:** `ghcr.io/linuxserver/wireguard:1.0.20250521` (pinned from running container label)

**Changes from OMV:**
- Image pinned
- Volume changed from `/appdata/wireguard/config` → `./config` (relative)

**Networks:** None (standalone — communicates directly via host port `51770:51820/udp`)

**Critical:** Config must be copied before cutover. If config is missing, WireGuard
regenerates all keys and all peer configs (QR codes + `.conf` files) must be
re-distributed to all 4 clients.

---

## .gitignore Additions

```
# Tailscale — binary runtime state
/infrastructure/tailscale/state/

# WireGuard — server + peer private keys (auto-generated on first run)
/infrastructure/wireguard/config/
```

---

## Implementation Steps

### Phase 1: Inspect running containers
1. `docker inspect update` → confirm WUD image version
2. `docker inspect wireguard` → confirm WireGuard image version

### Phase 2: Create GitOps files
3. Create `infrastructure/wud/compose.yaml`, `vars.env`; populate `.env`
4. Create `infrastructure/tailscale/compose.yaml`, `vars.env`; populate `.env`
5. Create `infrastructure/wireguard/compose.yaml`, `vars.env` (no `.env` needed)
6. Update `.gitignore`

### Phase 3: Copy state/config volumes
7. `sudo cp -a /appdata/tailscale/state/. infrastructure/tailscale/state/`
8. `sudo chown -R 1000:100 infrastructure/tailscale/state/`
9. `sudo cp -a /appdata/wireguard/config/. infrastructure/wireguard/config/`
10. `sudo chown -R 1000:100 infrastructure/wireguard/config/`

### Phase 4: Validate syntax
11. `docker compose -f infrastructure/wud/compose.yaml config`
12. `docker compose -f infrastructure/tailscale/compose.yaml config`
13. `docker compose -f infrastructure/wireguard/compose.yaml config`

### Phase 5: Cutover (one at a time)
14. Stop OMV WUD → `docker compose -f infrastructure/wud/compose.yaml up -d`
    Verify: `https://update.internal.pippinn.me`
15. Stop OMV Tailscale → `docker compose -f infrastructure/tailscale/compose.yaml up -d`
    Verify: `docker exec tailscale tailscale status`
16. Stop OMV WireGuard → `docker compose -f infrastructure/wireguard/compose.yaml up -d`
    Verify: `docker logs wireguard` (no key regeneration; existing peer configs still valid)

### Phase 6: Commit & Document
17. Git commit all new files
18. Create `specs/05-infrastructure-services/summary.md`

---

## Risks

- **WireGuard key regeneration**: Copy config before starting. New keys = all 4 peers
  need redistributed configs.
- **Tailscale re-auth**: Copy state before starting. One-time auth keys will be consumed;
  expired keys require a new key from the Tailscale admin console.
- **WUD GitHub PAT**: Token was in plain text in OMV compose. Moved to `.env`. Do not
  commit the token value.
- **WireGuard no Docker network**: Intentional — standalone VPN. No Traefik integration.

---

## Rollback Plan (per service)

1. `docker compose -f infrastructure/<service>/compose.yaml down`
2. Re-enable OMV stack in OMV UI
3. State/config preserved on disk — no data loss
