# Milestone 06.9 Plan: Home Assistant Stack Migration

**Date:** 2026-03-25
**Status:** `READY`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate the Home Assistant stack (homeassistant, matter-server, ord_dagsins)
from `/appdata/home-assistant/` into `services/home-assistant/`.

---

## 📦 State to Migrate

| Source | Size | Target |
|--------|------|--------|
| `/appdata/home-assistant/config/` | 159MB | `services/home-assistant/config/` |
| `/appdata/home-assistant/matter-server/` | 1.2MB | `services/home-assistant/matter-server/` |

Both dirs gitignored, covered by BorgBackup.

---

## 🖼️ Image Pinning

| Container | Image | Note |
|-----------|-------|------|
| homeassistant | `ghcr.io/home-assistant/home-assistant:2026.3.2` | Already pinned |
| matter-server | `ghcr.io/home-assistant-libs/python-matter-server:stable` | No semver tags — keep `:stable`, known tech debt |
| ord_dagsins | `katur/ord_dagsins` | No tags available — unpinned, known tech debt |

---

## 🌐 Traefik Routing

| Container | Router | Entrypoints | Middleware |
|-----------|--------|-------------|------------|
| homeassistant | `home-assistant` | `websecure,tunnel` | none — HA has its own auth |
| homeassistant | — | — | `loadbalancer.server.url=http://host.docker.internal:8123` |
| ord_dagsins | `ord-dagsins` | `websecure,tunnel` | none |

⚠️ **Red-team:** Both HA and ord_dagsins are externally exposed via tunnel with
no Authelia. HA's own auth is the only protection. Intentional — confirmed by user
in milestone planning.

---

## 🔧 Special Configuration

### `network_mode: host`
Both `homeassistant` and `matter-server` use `network_mode: host`. This means:
- They are **not** attached to `traefik_internal` — `traefik.docker.network` is meaningless and must NOT be used
- Traefik reaches HA via `host.docker.internal:8123` (mapped to `172.17.0.1` in the gateway via `extra_hosts`)
- Use `traefik.http.services.home-assistant.loadbalancer.server.url=http://host.docker.internal:8123` instead
- matter-server has no Traefik labels — only reachable by HA via localhost

### USB Device
- `/dev/ttyUSB0:/dev/ttyUSB0` on homeassistant — Zigbee/Z-Wave stick
- OMV path is stable (udev persistent naming not confirmed — document as risk)

### ord_dagsins
- Stateless container, no volumes
- Port 3000 exposed internally
- No semver tags — pinned by digest
- Connected to `traefik_internal` network only

---

## 🔒 Secrets

None — no `.env` file needed for this stack.

---

## 🔁 Cutover Steps

1. Create `services/home-assistant/compose.yaml`
2. `docker compose config` — validate
3. Stop containers: `docker stop homeassistant matter-server ord_dagsins && docker rm homeassistant matter-server ord_dagsins`
4. Copy state:
   ```bash
   sudo cp -a /appdata/home-assistant/config   services/home-assistant/config
   sudo cp -a /appdata/home-assistant/matter-server services/home-assistant/matter-server
   sudo chown -Rh 1000:100 services/home-assistant/config
   sudo chown -Rh 1000:100 services/home-assistant/matter-server
   ```
5. `docker compose up -d`
6. Verify HA UI accessible, automations intact, Matter devices connected

---

## 🔁 Rollback

1. `docker stop homeassistant matter-server ord_dagsins && docker rm homeassistant matter-server ord_dagsins`
2. `sudo docker compose -f /appdata/home-assistant/<file>.yml up -d`
3. `/appdata/` data untouched until confirmed stable

---

## ✅ Success Criteria

- [ ] All three containers running from `services/home-assistant/`
- [ ] `home-assistant.pippinn.me` accessible internally and via tunnel
- [ ] `ord-dagsins.pippinn.me` accessible
- [ ] Automations, scripts, and integrations intact
- [ ] Matter devices still connected
- [ ] Zigbee/Z-Wave USB device functional
