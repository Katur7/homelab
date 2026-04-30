# Milestone 15: Summary — Replace Mealie with Flatnotes

## What Changed
- Removed `services/mealie/` (compose.yaml + vars.env).
- Added `services/flatnotes/` with `compose.yaml` mounting `./data:/app/data`.
- Flatnotes exposed at `recipes.pippinn.me` on two routers:
  - `flatnotes-internal` — `websecure` entrypoint, LAN-only via global middleware.
  - `flatnotes-tunnel` — `tunnel` entrypoint, Authelia gated (`authelia-auth@file`).
- `FLATNOTES_AUTH_TYPE=none` — Authelia is sole gatekeeper, no Flatnotes credentials.
- Memory capped at 128 MB. WUD autoupdate enabled.
- Image pinned: `dullage/flatnotes:v5.5.4`.

## Why
Mealie (~150–300 MB idle) was unused and over-engineered for the actual use case: occasionally storing and browsing recipes as markdown. Flatnotes (~20 MB idle) covers the use case with zero operational overhead.

## Data Migration
None required — Mealie had zero recipes at time of removal.

## New Secrets / Variables
None.

## Architecture / global.env Updates Needed
None.
