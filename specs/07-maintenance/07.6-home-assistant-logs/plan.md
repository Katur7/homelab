# Milestone 07.6 Plan: Home Assistant — Log Audit & Error Fix

**Date:** 2026-03-29
**Status:** `PLANNED`

---

## Problem

Home Assistant has been running since Milestone 06.9 but its logs have not been reviewed.
Errors and warnings in `homeassistant.log` can indicate broken integrations, deprecated
config, or device communication failures — all of which degrade reliability silently.

---

## Known Issues to Check

- Deprecated YAML config keys (HA removes legacy config between versions).
- Integration failures on `/dev/ttyUSB0` (Z-Wave/Zigbee USB stick).
- Matter server connection health.
- `matter-server` is pinned to `:stable` — pin violation to fix regardless of log findings.

---

## Fix Process

1. Pull current logs:
   ```
   docker logs homeassistant --tail 300 2>&1 | grep -E "ERROR|WARNING|CRITICAL"
   docker exec homeassistant grep -E "ERROR|WARNING|CRITICAL" /config/home-assistant.log | tail -100
   ```

2. Triage each unique error:
   - **Fix in this milestone:** broken integration config, deprecated YAML key, missing env.
   - **Defer:** upstream HA bugs, unsupported hardware, future feature scope.

3. Apply fixes to `services/home-assistant/config/` YAML files as needed.

4. Pin `matter-server` from `:stable` → `6.2.2` (latest stable as of 2026-03-29).
   - Note: `matter-server` image pin is being handled in 07.2 as part of the WUD pass.
     If 07.2 runs first, this step is already done.

5. Restart HA and verify no new errors appear:
   ```
   docker compose up -d  # in services/home-assistant/
   docker logs homeassistant --tail 100
   ```

---

## Files to Change

| File | Change |
|------|--------|
| `services/home-assistant/compose.yaml` | Pin `matter-server` (if not done in 07.2) |
| `services/home-assistant/config/configuration.yaml` | Fix deprecated keys / broken config (as needed) |
| Other `config/*.yaml` | As discovered during log triage |

---

## Rollback

```
git stash  # revert any config file changes
docker compose up -d  # in services/home-assistant/
```
