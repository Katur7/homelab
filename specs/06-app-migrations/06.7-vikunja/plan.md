# Milestone 06.7 Plan: Vikunja Migration

**Date:** 2026-03-25
**Status:** `READY`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate Vikunja (todo app) and its Postgres database from `/appdata/Vikunja - ToDo/`
into `services/vikunja/`. Key work beyond a straight copy: extract three secrets that
are hardcoded inline in the OMV compose into a `.env` file.

---

## 📦 State to Migrate

| Source | Size | Target |
|--------|------|--------|
| `/appdata/Vikunja - ToDo/files/` | 4KB | `services/vikunja/files/` |
| `/appdata/Vikunja - ToDo/db/` | 65MB | `services/vikunja/db/` |

Both dirs gitignored. The `db/` dir is a Postgres data directory — preserve
ownership with `cp -a` and do **not** chown (Postgres runs as its own internal UID).

---

## 🖼️ Image Pinning

| Container | Pin |
|-----------|-----|
| `vikunja/vikunja` | digest `sha256:214d1fcc189be68573477fb5ee8ca86fbdec177c54246f1b8c9b99bf457bdc74` |
| `postgres:17` | digest `sha256:f7b9342239186c2854750ea707616498f95da3751b20001f1b7e2dd61afefff4` |

---

## 🌐 Traefik Routing

| Router | Entrypoint | Rule | Middleware |
|--------|-----------|------|------------|
| `todo-internal` | `websecure` | `Host(\`todo.pippinn.me\`)` | none (internal-only global chain) |
| `todo-tunnel` | `tunnel` | `Host(\`todo.pippinn.me\`)` | `authelia-auth@file` |

---

## 🔒 Secrets Extraction

The OMV compose has three secrets hardcoded inline. All move to `.env`:

| Variable | Goes to |
|----------|---------|
| `VIKUNJA_DATABASE_PASSWORD` | `.env` |
| `VIKUNJA_SERVICE_JWTSECRET` | `.env` |
| `POSTGRES_PASSWORD` | `.env` |

`vars.env` (tracked in Git) holds only non-sensitive config:
- `VIKUNJA_SERVICE_PUBLICURL=https://todo.pippinn.me`
- `VIKUNJA_SERVICE_ENABLEREGISTRATION=false`
- `VIKUNJA_DATABASE_HOST=db`
- `VIKUNJA_DATABASE_TYPE=postgres`
- `VIKUNJA_DATABASE_USER=vikunja`
- `VIKUNJA_DATABASE_DATABASE=vikunja`

---

## ⚠️ Postgres Ownership Warning

The `db/` directory is owned by the Postgres internal UID (typically 999).
- Copy with `cp -a` to preserve ownership
- Do **not** run `chown` on `db/` — Postgres will fail to start if ownership changes
- Verify with `ls -lan services/vikunja/db/` after copy

---

## 🔁 Cutover Steps

1. Create `services/vikunja/compose.yaml`, `vars.env`, `.env`
2. `docker compose config` — validate
3. Stop containers: `docker stop vikunja vikunja-db && docker rm vikunja vikunja-db`
4. Copy state:
   ```bash
   sudo cp -a "/appdata/Vikunja - ToDo/files" services/vikunja/files
   sudo cp -a "/appdata/Vikunja - ToDo/db"    services/vikunja/db
   ```
5. Verify `db/` ownership is NOT 1000 (should be postgres UID ~999)
6. `docker compose up -d`
7. Verify both containers healthy, `todo.pippinn.me` accessible internally and externally

---

## 🔁 Rollback

1. `docker stop vikunja vikunja-db && docker rm vikunja vikunja-db`
2. `sudo docker compose --env-file "/appdata/Vikunja - ToDo/Vikunja - ToDo.env" -f "/appdata/Vikunja - ToDo/Vikunja - ToDo.yml" up -d`
3. Data in `/appdata/Vikunja - ToDo/` untouched until confirmed stable

---

## ✅ Success Criteria

- [ ] Both containers running from `services/vikunja/`
- [ ] `todo.pippinn.me` accessible internally (`websecure`)
- [ ] `todo.pippinn.me` accessible externally via tunnel, Authelia login required
- [ ] Existing tasks/projects visible — no data loss
- [ ] No secrets in `compose.yaml` or `vars.env`
