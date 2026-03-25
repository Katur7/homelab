# Milestone 06.7 Summary: Vikunja Migration

**Date:** 2026-03-25
**Status:** `COMPLETE`

Migrated Vikunja and its Postgres database from `/appdata/Vikunja - ToDo/`
into `services/vikunja/`. Secrets extracted from inline OMV compose to `.env`.

**Notable:**
- `files/` ownership fixed 1001→1000 before start
- Digest pinning failed (Docker Hub manifest schema); switched to `vikunja:2.2.2` and `postgres:17`
- `user: 1000:100` set explicitly on vikunja container

**New secrets in `.env`:** `VIKUNJA_DATABASE_PASSWORD`, `VIKUNJA_SERVICE_JWTSECRET`, `POSTGRES_PASSWORD`

**ARCHITECTURE.md update:** No.
