# Milestone 06 Plan: Application Service Migrations

**Date:** 2026-03-24
**Status:** `READY — Pre-migration issues resolved`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate all remaining OMV-managed application stacks from `/appdata/` into the
GitOps-controlled `services/` directory. Each sub-milestone is one cohesive stack.

After this milestone, `docker ps` should show zero containers with a working
directory under `/appdata/`, and **no service state should remain under `/appdata/`**.

---

## 🏗️ Volume Strategy

All state and config data moves from `/appdata/` into the service folder under
`/home/grimur/homelab/services/<service>/`. These subdirectories are **gitignored**
(binary/large/sensitive data) but covered by the existing BorgBackup job which
sources `/home/grimur/homelab/`.

**What moves to `services/<service>/`** (gitignored subdirs):

| Service | `/appdata/` source | GitOps target | Notes |
|---------|-------------------|--------------|-------|
| mealie | `mealie/data/` | `services/mealie/data/` | Recipe DB + assets |
| calibre-web | `calibre-web/config/` | `services/calibre-web/config/` | App config/db |
| plex | `Plex/config/` | `services/plex/config/` | Metadata cache (can be GBs) |
| radarr | `StarArr/radar-config/` | `services/starr/radarr-config/` | App config/db |
| sonarr | `StarArr/sonarr-config/` | `services/starr/sonarr-config/` | App config/db |
| prowlarr | `StarArr/prowlarr-config/` | `services/starr/prowlarr-config/` | App config/db |
| qbittorrent | `StarArr/qbittorrent-config/` | `services/starr/qbittorrent-config/` | App config/db |
| syncthing | `syncthing/config/` | `services/syncthing/config/` | Device keys + DB |
| vikunja | `Vikunja - ToDo/files/` | `services/vikunja/files/` | Uploaded attachments |
| vikunja-db | `Vikunja - ToDo/db/` | `services/vikunja/db/` | Postgres data dir |
| audiobookshelf | `audiobookshelf/config/` | `services/audiobookshelf/config/` | App config/db |
| audiobookshelf | `audiobookshelf/metadata/` | `services/audiobookshelf/metadata/` | Metadata cache |
| homeassistant | `home-assistant/config/` | `services/home-assistant/config/` | HA state + automations |
| matter-server | `home-assistant/matter-server/` | `services/home-assistant/matter-server/` | Matter controller state |
| immich-db | `Immich/immich-database/` | `services/immich/database/` | Postgres data dir |

**What stays on UUID NAS paths** (bulk media — too large to move, NAS-managed):

| Data | Path |
|------|------|
| Photos | `/srv/dev-disk-by-uuid-0ddafbf7-.../photos` |
| Movies | `/srv/dev-disk-by-uuid-f1209e02-.../movies` |
| TV | `/srv/dev-disk-by-uuid-220b73c9-.../tv` |
| Kids | `/srv/dev-disk-by-uuid-0ddafbf7-.../kids` |
| Books / Ebooks | `/srv/dev-disk-by-uuid-f1209e02-.../books` |
| Downloads | `/srv/dev-disk-by-uuid-f1209e02-.../downloads-*` |

---

## 🔒 .gitignore Strategy

Each service folder that has state data gets its subdirs gitignored.
The pattern follows the existing WireGuard/Tailscale precedent.

Entries to add to `/home/grimur/homelab/.gitignore`:

```gitignore
# --- Service state (gitignored, covered by BorgBackup) ---
/services/mealie/data/
/services/calibre-web/config/
/services/plex/config/
/services/starr/radarr-config/
/services/starr/sonarr-config/
/services/starr/prowlarr-config/
/services/starr/qbittorrent-config/
/services/syncthing/config/
/services/vikunja/files/
/services/vikunja/db/
/services/audiobookshelf/config/
/services/audiobookshelf/metadata/
/services/home-assistant/config/
/services/home-assistant/matter-server/
/services/immich/database/
```

---

## 📦 Data Migration Process (Per Sub-Milestone)

For every service with state data, before starting the new GitOps stack:

```bash
# 1. Stop the old OMV-managed stack
docker compose -f /appdata/<service>/<service>.yml down

# 2. Copy state to GitOps location (preserve permissions + ownership)
cp -a /appdata/<source>/ /home/grimur/homelab/services/<service>/<target>/

# 3. Verify ownership (should be 1000:100 for app data, root for postgres dirs is OK)
ls -la /home/grimur/homelab/services/<service>/

# 4. Start the new GitOps stack
docker compose -f /home/grimur/homelab/services/<service>/compose.yaml up -d

# 5. Verify service health, then remove /appdata/ source (after confirmation)
```

> **Postgres note:** Postgres data directories (`vikunja/db/`, `immich/database/`) are
> owned by the postgres user inside the container (UID 999 typically). `cp -a` preserves
> this — do not `chown` these directories.

---

## ✅ Pre-Migration: Resolved Issues

### 1. PUID / TZ — RESOLVED
- **PUID=1000**, PGID=100 confirmed correct.
- **TZ=Europe/Stockholm** confirmed. `global.env` updated from `Atlantic/Stockholm`.

### 2. Shared Volume Variables — RESOLVED
`DATA_KIDS`, `DATA_MOVIES`, `DATA_TV` are hardcoded directly in each service's
`compose.yaml`. These vars are not in `global.env` — Docker Compose `env_file`
only injects variables into the container environment, not into compose file
variable substitution (volume paths). Hardcoding the UUID paths is the correct
approach since they are fixed hardware constants.

### 3. Image Pinning — Standing Rule

All services pinned to their running versions during migration. Images captured below.

| Service | Current Image | Pin To |
|---------|--------------|--------|
| radarr | `ghcr.io/linuxserver/radarr:latest` | `6.0.4.10291-ls295` |
| sonarr | `ghcr.io/linuxserver/sonarr:latest` | `4.0.17.2952-ls305` |
| prowlarr | `linuxserver/prowlarr:latest` | `2.3.0.5236-ls139` |
| qbittorrent | `ghcr.io/linuxserver/qbittorrent:latest` | `5.1.4-r2-ls446` |
| plex | `ghcr.io/linuxserver/plex:latest` | `1.43.0.10492-121068a07-ls297` |
| mealie | `ghcr.io/mealie-recipes/mealie:latest` | `v3.13.1` |
| syncthing | `ghcr.io/linuxserver/syncthing:latest` | `v2.0.15-ls211` |
| calibre-web | `ghcr.io/linuxserver/calibre-web:latest` | `0.6.26-ls375` |
| audiobookshelf | `ghcr.io/advplyr/audiobookshelf:latest` | `2.33.1` |
| vikunja | `vikunja/vikunja` *(no tag)* | digest `sha256:214d1fcc189be68573477fb5ee8ca86fbdec177c54246f1b8c9b99bf457bdc74` |
| ord_dagsins | `katur/ord_dagsins` *(no tag)* | digest — resolve at migration time |
| matter-server | `ghcr.io/home-assistant-libs/python-matter-server:stable` | no semver — keep `:stable`, document |
| immich-server | `ghcr.io/immich-app/immich-server:release` | resolve latest semver tag at migration time |
| immich-ml | `ghcr.io/immich-app/immich-machine-learning:release` | same as immich-server |

### 4. Hardcoded Secrets in Vikunja Compose — TO FIX DURING 06.7
`VIKUNJA_DATABASE_PASSWORD` and `VIKUNJA_SERVICE_JWTSECRET` are inline in the OMV
compose. Must be extracted to `.env` during migration.

---

## 🗂️ Sub-Milestones (Ordered: Simple → Complex)

| # | Sub-milestone | Services | Complexity | External? | Secrets? | State to move? |
|---|---------------|----------|------------|-----------|---------|----------------|
| 06.1 | IT-Tools | `tools` | Low | ❌ | ❌ | ❌ None |
| 06.2 | Mealie | `mealie` | Low | ❌ | ❌ | ✅ `data/` |
| 06.3 | Calibre-web | `calibre-web` | Low | ❌ | ❌ | ✅ `config/` |
| 06.4 | Plex | `plex` | Low-Med | ❌ | ❌ | ✅ `config/` (large) |
| 06.5 | StarArr | radarr, sonarr, prowlarr, qbittorrent | Medium | ❌ | ❌ | ✅ 4× config dirs |
| 06.6 | Syncthing | `syncthing` | Medium | ❌ | ❌ | ✅ `config/` |
| 06.7 | Vikunja | `vikunja`, `vikunja-db` | Medium | ✅ Authelia | ✅ | ✅ `files/` + `db/` |
| 06.8 | Audiobookshelf | `audiobookshelf` | Medium | ✅ Lissen bypass | ✅ | ✅ `config/` + `metadata/` |
| 06.9 | Home Assistant | homeassistant, matter-server, ord_dagsins | High | ✅ (no Authelia) | ❌ | ✅ `config/` + `matter-server/` |
| 06.10 | Immich | 4 containers | High | ✅ OIDC bypass | ✅ | ✅ `database/` |

---

## 📋 Per-Sub-Milestone Details

### 06.1 — IT-Tools
**Target:** `services/it-tools/`
**State to move:** None

- Already version-pinned: `corentinth/it-tools:2024.10.22-7ca5933`
- Internal only, no secrets, stateless
- `vars.env`: empty (all config via labels)

---

### 06.2 — Mealie
**Target:** `services/mealie/`
**State to move:** `/appdata/mealie/data/` → `services/mealie/data/`

- Pin image: `ghcr.io/mealie-recipes/mealie:v3.13.1`
- `vars.env`: `ALLOW_SIGNUP=false`, `BASE_URL=https://mealie.internal.pippinn.me`
- Preserve `deploy.resources.limits.memory: 500M`
- Gitignore: `/services/mealie/data/`

---

### 06.3 — Calibre-web
**Target:** `services/calibre-web/`
**State to move:** `/appdata/calibre-web/config/` → `services/calibre-web/config/`

- Pin image: `ghcr.io/linuxserver/calibre-web:0.6.26-ls375`
- Ebooks NAS path stays absolute: `/srv/.../books/ebooks:/ebooks:ro`
- `vars.env`: `OAUTHLIB_RELAX_TOKEN_SCOPE=1`
- Gitignore: `/services/calibre-web/config/`

---

### 06.4 — Plex
**Target:** `services/plex/`
**State to move:** `/appdata/Plex/config/` → `services/plex/config/` *(warn: can be several GB)*

- Pin image: `ghcr.io/linuxserver/plex:1.43.0.10492-121068a07-ls297`
- Media stays on NAS paths via `DATA_KIDS`, `DATA_MOVIES`, `DATA_TV`
- Direct ports: `32400:32400`, `32410-32414/udp` preserved
- `vars.env`: `VERSION=docker`, `LOCAL_IPS=192.168.86.0/24,10.13.13.0/24,172.25.0.0/24`, `PLEX_PORT=32400`
- Traefik: internal only — `plex.internal.pippinn.me` on `websecure`, port 32400
- Gitignore: `/services/plex/config/`

---

### 06.5 — StarArr
**Target:** `services/starr/`
**State to move:**
- `/appdata/StarArr/radar-config/` → `services/starr/radarr-config/`
- `/appdata/StarArr/sonarr-config/` → `services/starr/sonarr-config/`
- `/appdata/StarArr/prowlarr-config/` → `services/starr/prowlarr-config/`
- `/appdata/StarArr/qbittorrent-config/` → `services/starr/qbittorrent-config/`

- Pin all 4 images (versions in table above)
- Media via `DATA_KIDS`, `DATA_MOVIES`, `DATA_TV` + hardcoded download paths
- All internal-only routes on `websecure`
- qBittorrent: direct port `32517:32517`
- `vars.env`: `TORRENTING_PORT=32517`
- **Note:** `prowlarr` image has no `ghcr.io` prefix — keep `linuxserver/prowlarr` to avoid registry switch risk
- Gitignore: 4× config dirs

---

### 06.6 — Syncthing
**Target:** `services/syncthing/`
**State to move:** `/appdata/syncthing/config/` → `services/syncthing/config/`

- Pin image: `ghcr.io/linuxserver/syncthing:v2.0.15-ls211`
- Sync folders stay on NAS paths via `DATA_*` vars + hardcoded absolute paths
- Ports: `22000:22000/tcp+udp`, `21027:21027/udp` preserved
- Traefik: `sync.internal.pippinn.me` on `websecure`, port 8384
- Gitignore: `/services/syncthing/config/`

---

### 06.7 — Vikunja
**Target:** `services/vikunja/`
**State to move:**
- `/appdata/Vikunja - ToDo/files/` → `services/vikunja/files/`
- `/appdata/Vikunja - ToDo/db/` → `services/vikunja/db/` *(Postgres data dir — preserve ownership)*

- Pin vikunja by digest: `vikunja/vikunja@sha256:214d1fcc189be68573477fb5ee8ca86fbdec177c54246f1b8c9b99bf457bdc74`
- Pin postgres: `postgres:17` + digest `sha256:f7b9342239186c2854750ea707616498f95da3751b20001f1b7e2dd61afefff4`
- **Secrets → `.env`:**
  - `VIKUNJA_DATABASE_PASSWORD`
  - `VIKUNJA_SERVICE_JWTSECRET`
  - `POSTGRES_PASSWORD`
- `vars.env`: `VIKUNJA_SERVICE_PUBLICURL=https://todo.pippinn.me`, `VIKUNJA_SERVICE_ENABLEREGISTRATION=false`, non-secret DB params
- Traefik: `websecure` (internal) + `tunnel` with `authelia-auth@file`
- Gitignore: `/services/vikunja/files/`, `/services/vikunja/db/`

---

### 06.8 — Audiobookshelf
**Target:** `services/audiobookshelf/`
**State to move:**
- `/appdata/audiobookshelf/config/` → `services/audiobookshelf/config/`
- `/appdata/audiobookshelf/metadata/` → `services/audiobookshelf/metadata/`

- Pin image: `ghcr.io/advplyr/audiobookshelf:2.33.1`
- Media stays on NAS paths (audiobooks, ebooks — read-only mounts)
- **Secret → `.env`:** `LISSEN_APP_SECRET`
- Traefik: reproduce 4-router setup exactly:
  1. `audiobookshelf-internal` — `websecure`, internal access
  2. `audiobookshelf-handshake` — `tunnel`, header `X-Lissen-Secret`, priority 200
  3. `audiobookshelf-discovery` — `tunnel`, paths `/status`+`/api/languages`+`/api/server/settings`, priority 150
  4. `audiobookshelf-tunnel` — `tunnel`, `authelia-auth@file`, priority 100
- Gitignore: `/services/audiobookshelf/config/`, `/services/audiobookshelf/metadata/`

---

### 06.9 — Home Assistant
**Target:** `services/home-assistant/`
**State to move:**
- `/appdata/home-assistant/config/` → `services/home-assistant/config/`
- `/appdata/home-assistant/matter-server/` → `services/home-assistant/matter-server/`

- HA image already pinned: `ghcr.io/home-assistant/home-assistant:2026.3.2`
- `matter-server`: `ghcr.io/home-assistant-libs/python-matter-server:stable` — no semver tags; keep `:stable`, document
- `ord_dagsins`: `katur/ord_dagsins` — pin by digest resolved at migration time
- **`network_mode: host`** on HA and matter-server — requires `traefik.docker.network=traefik_internal` label on HA
- **USB device:** `/dev/ttyUSB0:/dev/ttyUSB0` — verify path is stable before migration
- Traefik: HA on `websecure` + `tunnel` (no Authelia — intentional, HA has its own auth)
- `ord_dagsins` on `websecure` + `tunnel` — confirm no Authelia is intentional
- **⚠️ Red-team:** HA exposed externally via tunnel with no Authelia. HA's own auth is the only protection. Acceptable if HA auth is configured and strong; worth a deliberate confirmation.
- Gitignore: `/services/home-assistant/config/`, `/services/home-assistant/matter-server/`

---

### 06.10 — Immich
**Target:** `services/immich/`
**State to move:**
- `/appdata/Immich/immich-database/` → `services/immich/database/` *(Postgres data dir — preserve ownership)*

- **Image pinning:** Resolve current Immich semver release at migration time. Use `IMMICH_VERSION=vX.Y.Z` in `vars.env`.
- Redis: preserve digest pin from OMV compose (`valkey/valkey:8-bookworm@sha256:fea8b3e6...`)
- Postgres: preserve digest pin from OMV compose (`ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:41eacbe8...`)
- `model-cache` Docker named volume: declare in compose — persists across migration automatically
- **Secrets → `.env`:**
  - `DB_PASSWORD`
  - `IMMICH_APP_AUTH_BYPASS_SECRET`
- `vars.env`: `UPLOAD_LOCATION`, `DB_DATA_LOCATION=./database`, `DB_USERNAME=postgres`, `DB_DATABASE_NAME=immich`, `IMMICH_VERSION`
- Traefik: reproduce 4-router setup exactly:
  1. `photos-internal` — `websecure`, internal access
  2. `photos-tunnel` — `tunnel`, `authelia-auth@file`, priority 100
  3. `photos-app` — `tunnel`, header `X-Immich-App-Secret`, priority 150
  4. `photos-app-login` — `tunnel`, paths `/.well-known/immich` + `/api/server/ping`, priority 200
- Gitignore: `/services/immich/database/`

---

## 🔁 Rollback Strategy (All Sub-Milestones)

1. State data is **copied**, not moved — `/appdata/` source is kept until confirmed stable
2. On failure: `docker compose -f /appdata/<service>/<service>.yml up -d` restores service
3. Each sub-milestone is independent — failure in one does not affect others
4. Remove `/appdata/` source only after user confirms the migrated service is stable

---

## ✅ Success Criteria

- [ ] `docker ps` shows 0 containers with working dir in `/appdata/`
- [ ] No service volume mounts reference `/appdata/`
- [ ] All services accessible at their expected URLs
- [ ] All compose files under `/home/grimur/homelab/services/`
- [ ] All images pinned to specific versions (digest-pinned where no semver tag exists)
- [ ] All secrets in `.env` files (gitignored), none in `vars.env` or `compose.yaml`
- [ ] All state directories gitignored in `.gitignore`
- [ ] `ARCHITECTURE.md` updated to document the volume strategy
- [ ] `/appdata/` sources removed after each sub-milestone is confirmed stable

---

## 📋 ARCHITECTURE.md Updates Required

After completion:
- Update volume strategy section: state data lives in `services/<service>/` (gitignored, BorgBackup covered)
- Document the gitignore pattern for service state
- Remove `/appdata/` references
