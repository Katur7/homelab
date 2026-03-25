# Milestone 06.9 Summary: Home Assistant Stack Migration

**Date:** 2026-03-25
**Status:** `COMPLETE`

Migrated homeassistant, matter-server, and ord_dagsins from `/appdata/home-assistant/`
into `services/home-assistant/`. Config (159MB) and matter-server data (1.2MB) copied,
ownership fixed 1001→1000.

**Notable:**
- `traefik.docker.network` dropped for host-network containers — use
  `loadbalancer.server.url=http://host.docker.internal:8123` instead
- `ord_dagsins` unpinned (no tags available) — known tech debt
- `matter-server` kept at `:stable` (no semver tags available) — known tech debt

**Git-tracked HA config files:** `configuration.yaml`, `sensors/`, `templates/` — user-authored
files selectively un-ignored from the otherwise gitignored `config/` directory.

**New secrets:** None. **ARCHITECTURE.md update:** No.
