# Milestone 06.5 Plan: StarArr Stack Migration

**Date:** 2026-03-25
**Status:** `READY`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate the StarArr stack (Radarr, Sonarr, Prowlarr, qBittorrent) from
`/appdata/StarArr/` into `services/starr/`. All four containers currently
run from the same OMV project at `/appdata/StarArr/StarArr.yml`.

---

## 📦 State to Migrate

| Config dir | Size | Target |
|-----------|------|--------|
| `/appdata/StarArr/radar-config/` | 133M | `services/starr/radarr-config/` |
| `/appdata/StarArr/sonarr-config/` | 88M | `services/starr/sonarr-config/` |
| `/appdata/StarArr/prowlarr-config/` | 88M | `services/starr/prowlarr-config/` |
| `/appdata/StarArr/qbittorrent-config/` | 17M | `services/starr/qbittorrent-config/` |

Total: ~326MB — all four dirs gitignored, covered by BorgBackup.

---

## 🖼️ Image Pinning

| Container | Current image | Pin to |
|-----------|--------------|--------|
| radarr | `ghcr.io/linuxserver/radarr:latest` | `6.0.4.10291-ls295` |
| sonarr | `ghcr.io/linuxserver/sonarr:latest` | `4.0.17.2952-ls305` |
| prowlarr | `linuxserver/prowlarr:latest` | `2.3.0.5236-ls139` |
| qbittorrent | `ghcr.io/linuxserver/qbittorrent:latest` | `5.1.4-r2-ls446` |

Note: `prowlarr` keeps the `linuxserver/` (Docker Hub) prefix — switching to
`ghcr.io/linuxserver/prowlarr` at the same time as a migration is unnecessary
risk. Change separately if desired.

---

## 🌐 Networking & Traefik

All four services are **internal only** — `websecure` entrypoint, no tunnel exposure.

| Service | Internal URL |
|---------|-------------|
| radarr | `radarr.internal.pippinn.me` |
| sonarr | `sonarr.internal.pippinn.me` |
| prowlarr | `prowlarr.internal.pippinn.me` |
| qbittorrent | `torrent.internal.pippinn.me` |

qBittorrent also has a direct port: `32517:32517` (torrenting port — must be preserved).

---

## 💾 Volume Mounts (hardcoded UUID paths)

**Radarr:**
- `./radarr-config:/config`
- `/srv/dev-disk-by-uuid-f1209e02-.../movies:/movies`
- `/srv/dev-disk-by-uuid-f1209e02-.../downloads-movies:/downloads/movies`
- `/srv/dev-disk-by-uuid-0ddafbf7-.../kids/movies:/kids/movies`
- `/srv/dev-disk-by-uuid-f1209e02-.../downloads-kids-movies:/downloads/kids/movies`

**Sonarr:**
- `./sonarr-config:/config`
- `/srv/dev-disk-by-uuid-220b73c9-.../tv:/tv`
- `/srv/dev-disk-by-uuid-f1209e02-.../downloads-tv:/downloads/tv`

**Prowlarr:**
- `./prowlarr-config:/config`

**qBittorrent:**
- `./qbittorrent-config:/config`
- `/srv/dev-disk-by-uuid-f1209e02-.../downloads-movies:/downloads/movies`
- `/srv/dev-disk-by-uuid-f1209e02-.../downloads-tv:/downloads/tv`
- `/srv/dev-disk-by-uuid-0ddafbf7-.../kids:/downloads/kids`

---

## 🔒 Secrets

None — no `.env` file needed for this stack.

---

## ⚙️ vars.env

```env
TORRENTING_PORT=32517
```

PUID, PGID, TZ come from `../../global.env`.

---

## 🔁 Cutover Steps

1. Create `services/starr/compose.yaml` and `vars.env`
2. `docker compose config` — validate syntax
3. Stop all four containers: `docker stop radarr sonarr prowlarr qbittorrent && docker rm radarr sonarr prowlarr qbittorrent`
   - OMV compose can't be used to stop (same DATA_* interpolation issue as Plex)
4. Copy all four config dirs (note: `radar-config` → `radarr-config` fixes OMV typo):
   ```
   cp -a /appdata/StarArr/radar-config   services/starr/radarr-config
   cp -a /appdata/StarArr/sonarr-config  services/starr/sonarr-config
   cp -a /appdata/StarArr/prowlarr-config services/starr/prowlarr-config
   cp -a /appdata/StarArr/qbittorrent-config services/starr/qbittorrent-config
   ```
5. `docker compose up -d` from `services/starr/`
6. Verify all four containers running from GitOps path
7. Confirm all four UIs accessible

---

## 🔁 Rollback

1. `docker stop` / `docker rm` the new containers
2. Start OMV stack: `sudo docker compose --env-file /appdata/global.env -f /appdata/StarArr/StarArr.yml up -d`
3. Config dirs in `/appdata/StarArr/` are untouched until post-confirmation cleanup

---

## ✅ Success Criteria

- [ ] All four containers running from `services/starr/`
- [ ] `radarr.internal.pippinn.me`, `sonarr.internal.pippinn.me`, `prowlarr.internal.pippinn.me`, `torrent.internal.pippinn.me` accessible
- [ ] Port 32517 reachable for qBittorrent torrenting
- [ ] No config data lost (verify by checking existing entries in each app)
