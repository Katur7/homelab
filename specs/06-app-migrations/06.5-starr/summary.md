# Milestone 06.5 Summary: StarArr Stack Migration

**Date:** 2026-03-25
**Status:** `COMPLETE`

## What Was Done

Migrated the StarArr stack (Radarr, Sonarr, Prowlarr, qBittorrent) from
`/appdata/StarArr/` into `services/starr/`.

- Created `services/starr/compose.yaml` with all four services pinned to
  their running versions
- Created `services/starr/vars.env` with `TORRENTING_PORT=32517`
- Copied all four config dirs to `services/starr/` (326MB total)
- Stopped containers directly (`docker stop/rm`) — OMV compose could not
  resolve its own `DATA_*` vars without `/appdata/global.env`

## Key Decisions

- **`radar-config` → `radarr-config`**: Fixed OMV typo during migration.
  No service impact — Radarr only sees the container path `/config`.
- **`prowlarr` image prefix kept as `linuxserver/prowlarr`**: Avoiding a
  registry switch (Docker Hub → ghcr.io) during migration. Change separately.
- **WUD labels restored** on Radarr and Prowlarr from the original OMV compose.

## New Secrets / Variables

None.

## ARCHITECTURE.md Update Required?

No.
