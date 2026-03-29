# Milestone 06.11 Plan: Linguacafe Migration

**Date:** 2026-03-26
**Status:** `READY`
**Author:** grimur & NAS Helper (AI)

---

## 🎯 Objective

Migrate the Linguacafe stack (webserver, python-service, mysql) from
`/appdata/linguacafe/` into `services/linguacafe/`. Service is currently
stopped — no live cutover needed, just set up and start from GitOps.

---

## 📦 State to Migrate

| Source | Size | Target |
|--------|------|--------|
| `/appdata/linguacafe/database/` | 1.7GB | `services/linguacafe/database/` |
| `/appdata/linguacafe/storage/` | 7.2GB | `services/linguacafe/storage/` |

Both dirs gitignored, covered by BorgBackup.

> **MySQL note:** `database/` is owned by MySQL internal UID. Copy with `cp -a`,
> do **not** chown.

---

## 🖼️ Image Pinning

Cached local images confirmed at `v0.14.1` via OCI labels.

| Container | Pin |
|-----------|-----|
| webserver | `ghcr.io/simjanos-dev/linguacafe-webserver:v0.14.1` |
| python-service | `ghcr.io/simjanos-dev/linguacafe-python-service:v0.14.1` |
| mysql | `mysql:8.0-debian` |

---

## 🌐 Traefik Routing

Internal only — `linguacafe.internal.pippinn.me` on `websecure`.

---

## 📋 Log Management

Rotated logs (`*.log.1` through `*.log.8`) deleted before migration — freed ~6.8GB.
Current active logs kept. Going forward:

- `LOG_LEVEL=warning` in `vars.env` — reduces Laravel log noise
- `LOG_DAILY_DAYS=2` in `vars.env` — caps rotation to 2 files
- MySQL `--general-log=1` **removed** from compose — was logging every SQL query

---

## 🔒 Secrets → `.env`

The OMV compose uses default values for all DB credentials. These must be set
explicitly in `.env`:

| Variable | Note |
|----------|------|
| `DB_PASSWORD` | Currently defaults to `linguacafe` — confirm or rotate |
| `DB_ROOT_PASSWORD` | Currently defaults to `linguacafe` — confirm or rotate |

`vars.env` holds non-secret config: `DB_DATABASE`, `DB_USERNAME`, `DB_HOST`, `DB_PORT`.

---

## ⚠️ Red-team

The OMV compose uses default passwords (`linguacafe`) for the MySQL database.
These are trivial credentials on a service with 7.2GB of user data. **Strongly
recommend rotating before starting.** Service is internal-only so exposure is
limited, but worth addressing.

---

## 🔁 Cutover Steps

1. Create `services/linguacafe/compose.yaml`, `vars.env`, `.env`
2. `docker compose config` — validate
3. Copy state:
   ```bash
   sudo cp -a /appdata/linguacafe/database services/linguacafe/database
   sudo cp -a /appdata/linguacafe/storage   services/linguacafe/storage
   sudo chown -Rh 1000:100 services/linguacafe/storage
   ```
4. Verify `database/` ownership (MySQL internal UID — do NOT chown)
5. `docker compose up -d`
6. Verify all three containers healthy, `linguacafe.internal.pippinn.me` accessible

---

## ✅ Success Criteria

- [ ] All three containers running from `services/linguacafe/`
- [ ] `linguacafe.internal.pippinn.me` accessible
- [ ] Existing learning data intact
- [ ] No default passwords in production
