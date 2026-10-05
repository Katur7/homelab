# Photoframe

HTTP server serving a dynamically rendered/cached static PNG to an ESP32-S3 photo frame.

| Property | Value |
|----------|-------|
| Direct Port | `8088` (`http://photoframe.internal.pippinn.me:8088/current.png`) |
| Traefik HTTPS URL | `https://photoframe.internal.pippinn.me/current.png` |
| Source repo | [photoframe-server](https://github.com/Katur7/photoframe-server) |
| Clone path | `~/photoframe-server` on the NAS |
| DNS | Local DNS record on PiHole pointing `photoframe.internal.pippinn.me` to `192.168.86.17` |

## Architecture & Compose Pattern

The stack uses `build: .` — the compose file cannot be separated from the source tree it builds. Duplicating it here would create two files that drift. The primary compose file lives in the `photoframe-server` repository on the NAS.

### Reference Compose Definition (`~/photoframe-server/compose.yaml`):

```yaml
name: photoframe-server

services:
  photoframe:
    build: .
    container_name: photoframe_server
    restart: unless-stopped
    ports:
      - "8088:8088"
    networks:
      - traefik_internal
    env_file:
      - .env
    labels:
      - "traefik.enable=true"
      - "traefik.docker.network=traefik_internal"
      - "traefik.http.routers.photoframe-internal.entrypoints=websecure"
      - "traefik.http.routers.photoframe-internal.rule=Host(`photoframe.internal.pippinn.me`)"
      - "traefik.http.services.photoframe-internal.loadbalancer.server.port=8088"

networks:
  traefik_internal:
    external: true
```

## Deployment on NAS

```bash
cd ~
git clone https://github.com/Katur7/photoframe-server.git
cd photoframe-server

# Copy existing .env credentials from Pi
scp grimur@192.168.86.26:~/photoframe-server/.env .env

# Build and start container
docker compose up -d --build
```

## Update & Rollback

```bash
cd ~/photoframe-server
git pull
docker compose up -d --build
```

To rollback:
```bash
cd ~/photoframe-server
git checkout <previous-commit-sha>
docker compose up -d --build
```
