# Milestone 06.10 Plan: Immich Migration

**Date:** 2026-03-25
**Status:** `READY`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate the Immich stack (immich-server, immich-machine-learning, valkey/redis,
postgres) from `/appdata/Immich/` into `services/immich/`.

---

## 📦 State to Migrate

| Source | Size | Target | Note |
|--------|------|--------|------|
| `/appdata/Immich/immich-database/` | 414MB | `services/immich/database/` | Postgres data dir — preserve ownership (UID 999) |
| `immich_model-cache` (Docker volume) | unknown | keep as Docker named volume | ML models — recreates on first run, no need to migrate |

Photos stay on NAS: `/srv/dev-disk-by-uuid-0ddafbf7-.../photos`

---

## 🖼️ Image Pinning

| Container | Current | Pin to |
|-----------|---------|--------|
| immich-server | `ghcr.io/immich-app/immich-server:release` | `v2.6.1` |
| immich-machine-learning | `ghcr.io/immich-app/immich-machine-learning:release` | `v2.6.1` |
| valkey (redis) | `valkey/valkey:8-bookworm@sha256:fea8b3e6...` | keep digest pin (already pinned) |
| postgres | `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:41eacbe8...` | keep digest pin (already pinned) |

---

## 🌐 Traefik Routing (4 routers)

| Router | Entrypoint | Rule | Priority | Middleware |
|--------|-----------|------|----------|------------|
| `photos-internal` | `websecure` | `Host(\`photos.pippinn.me\`)` | — | none |
| `photos-tunnel` | `tunnel` | `Host(\`photos.pippinn.me\`)` | 100 | `authelia-auth@file` |
| `photos-app` | `tunnel` | `Host(\`photos.pippinn.me\`) && Header(\`X-Immich-App-Secret\`, ...)` | 150 | none |
| `photos-app-login` | `tunnel` | `Host(\`photos.pippinn.me\`) && (Path(\`/.well-known/immich\`) \|\| Path(\`/api/server/ping\`))` | 200 | none |

---

## 🔒 Secrets → `.env`

| Variable | Value |
|----------|-------|
| `DB_PASSWORD` | `m6@Md^79eD!BwM` |
| `POSTGRES_PASSWORD` | `m6@Md^79eD!BwM` |
| `IMMICH_APP_AUTH_BYPASS_SECRET` | `b12r3jFeeaWaGiDFi~cCAZUw9SoLlaWxWJiR9_NZmEGn4y8x` |

---

## 📋 vars.env (tracked in Git)

```env
IMMICH_VERSION=v2.6.1
UPLOAD_LOCATION=/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos
DB_USERNAME=postgres
DB_DATABASE_NAME=immich
```

`DB_DATA_LOCATION` is replaced by a direct `./database` volume mount — no longer needed as an env var.

---

## ⚠️ Postgres Ownership Warning

`database/` is owned by Postgres internal UID (999). Copy with `cp -a`, do **not** chown.

---

## 🔁 Cutover Steps

1. Create `services/immich/compose.yaml`, `vars.env`, `.env`
2. `docker compose config` — validate
3. Stop all four containers: `docker stop immich_server immich_machine_learning immich_redis immich_postgres && docker rm immich_server immich_machine_learning immich_redis immich_postgres`
4. Copy database:
   ```bash
   sudo cp -a /appdata/Immich/immich-database services/immich/database
   ```
5. Verify `database/` ownership is NOT 1000 (should be ~999)
6. `docker compose up -d`
7. Verify all four containers healthy, `photos.pippinn.me` accessible

---

## 🔁 Rollback

1. Stop new containers
2. `docker stop` / `docker rm` new stack
3. Restore OMV containers manually (OMV compose has same DATA_* issue — stop directly and re-run)
4. `database/` in `/appdata/Immich/` untouched until confirmed stable

---

## ✅ Success Criteria

- [ ] All four containers running from `services/immich/`
- [ ] `photos.pippinn.me` accessible internally and via tunnel
- [ ] Authelia required for browser tunnel access
- [ ] Mobile app connects via `X-Immich-App-Secret` header bypass
- [ ] All photos, albums, and faces intact
- [ ] ML face recognition still functional
