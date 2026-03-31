# Milestone 08.5 Summary: Docker Auto-Updates via Cron

**Date:** 2026-03-31
**Status:** Complete

## What Was Changed

- `pi/scripts/update-containers.sh` made executable (`chmod +x`)
- Cron entry added to `grimur` crontab:
  `0 3 * * 3 /home/grimur/homelab/pi/scripts/update-containers.sh`
  Runs every Wednesday at 3am — pulls latest repo config, then pulls and restarts any updated images

## Image Tag Strategy

| Service | Tag | Reason |
|---------|-----|--------|
| `pihole` | `:latest` | Backup DNS only; NAS PiHole covers downtime during restart |
| `nebula-sync` | `:latest` | Small utility; no stable versioned tag available |
| `uptime-kuma` | `:2` | Major-version float; stable within v2.x |

## New Secrets/Variables
None.

## Architecture/global.env Updates Required
None.
