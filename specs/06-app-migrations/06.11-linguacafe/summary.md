# Milestone 06.11 Summary: Linguacafe Migration

**Date:** 2026-03-29
**Status:** `COMPLETE`

---

## What Was Changed

Migrated the Linguacafe stack (webserver, python-service, mysql) from
`/appdata/linguacafe/` into `services/linguacafe/`. Service was stopped prior
to migration — no live cutover.

Files created:
- `services/linguacafe/compose.yaml`
- `services/linguacafe/vars.env`
- `services/linguacafe/.env` (gitignored)
- `.gitignore` — added `database/` and `storage/` entries

State copied:
- `/appdata/linguacafe/database/` → `services/linguacafe/database/` (`cp -a`, no chown)
- `/appdata/linguacafe/storage/` → `services/linguacafe/storage/` (`chown -Rh 1000:100` applied)

---

## Why It Was Changed

Final remaining service running from `/appdata/`. Brings all application stacks
under GitOps control in `services/`.

---

## Issues Encountered

**MySQL password mismatch:** MySQL ignores `MYSQL_PASSWORD` env var when the
data directory already exists (only used for first-time init). The database was
migrated with the old default password (`linguacafe`), but `.env` was set to
a new strong password. Fixed by connecting as root with the old password and
running `ALTER USER` to rotate both `linguacafe` and `root` passwords in-place
before restarting the webserver.

**DB_HOST change:** Old OMV stack used `DB_HOST=linguacafe-database` (container
name). New compose uses the service name `mysql`. No stored config in `storage/`
referenced the old hostname, so no fixup was needed.

---

## New Secrets Created

| Variable | Location |
|----------|----------|
| `DB_PASSWORD` | `services/linguacafe/.env` |
| `DB_ROOT_PASSWORD` | `services/linguacafe/.env` |

Both rotated from the default `linguacafe` value to strong random passwords.

---

## ARCHITECTURE.md Update

No update required — volume strategy already documented from milestone 06.10.
