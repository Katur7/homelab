# Milestone 06.10 Summary: Immich Migration

**Date:** 2026-03-26
**Status:** `COMPLETE`

Migrated Immich (server, machine-learning, redis, postgres) from `/appdata/Immich/`
into `services/immich/`. Postgres data dir (414MB) copied, ownership preserved (UID 999).
`immich_model-cache` Docker volume retained as-is — no migration needed.

**Notable:**
- `IMMICH_VERSION` defined once in `.env`, referenced in compose via `${IMMICH_VERSION:-v2.6.1}`
- `DB_USERNAME`/`DB_DATABASE_NAME` hardcoded in `environment:` block — compose-level variable
  substitution only reads `.env`, not `env_file`
- Redis and Postgres kept on existing digest pins from OMV compose

**New secrets in `.env`:** `IMMICH_VERSION`, `DB_PASSWORD`, `IMMICH_APP_AUTH_BYPASS_SECRET`

**ARCHITECTURE.md update:** Yes — see milestone 06 completion notes.
