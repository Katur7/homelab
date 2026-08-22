# Photoframe

HTTP server serving a static PNG to an ESP32-S3 photo frame.

| Property | Value |
|----------|-------|
| Port | 8088 |
| URL | `http://photoframe.internal.pippinn.me:8088/current.png` |
| Source repo | [photoframe-server](https://github.com/Katur7/photoframe-server) |
| Clone path | `~/photoframe-server` on the Pi |
| DNS | Local DNS record on NAS PiHole, synced to Pi via nebula-sync |

## No compose.yaml in this repo

The stack uses `build: .` — the compose file cannot be separated from the source tree it builds.
Duplicating it here would create two files that drift. The real compose file lives in the
photoframe-server repo.

## Deploy

```bash
cd ~/photoframe-server
git pull
docker compose up -d --build
```

## Rollback

```bash
cd ~/photoframe-server
git checkout <previous-sha>
docker compose up -d --build
```

## Not in update-containers.sh

The Pi's `update-containers.sh` runs `docker compose pull`, but this image is locally built —
there is no upstream to pull. Updates come from `git pull` + rebuild in the photoframe-server repo.
