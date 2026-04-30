# Milestone 13: External Exposure — Summary

## What Was Changed

### 13.A — Recipes (Flatnotes, deviation from plan)

**Deviation:** Mealie was replaced with Flatnotes at `recipes.pippinn.me`. Mealie (`services/mealie/`) was removed entirely; Flatnotes (`services/flatnotes/`) was introduced as the recipes service.

- `services/mealie/compose.yaml` and `services/mealie/vars.env` deleted.
- `services/flatnotes/` added with dual-router Traefik config:
  - `websecure`: `recipes.pippinn.me` — LAN only (global `internal-only` middleware)
  - `tunnel`: `recipes.pippinn.me` — external, protected by Authelia `two_factor`
- PiHole DNS: `recipes.pippinn.me` added.
- Cloudflare Tunnel: public hostname `recipes.pippinn.me` added.

### 13.B — Home Assistant

- `services/home-assistant/compose.yaml` updated: single combined router split into two.
  - `home-assistant-internal` (`websecure`): full path, LAN only.
  - `home-assistant-tunnel` (`tunnel`): restricted to `PathPrefix('/api/webhook/')`, no Authelia.
- Cloudflare Tunnel: public hostname `home-assistant.pippinn.me` added.
- Companion app notification actions work externally; HA UI and full API are not reachable externally (VPN required).

## Why

- Flatnotes chosen over Mealie — simpler, markdown-native, better fit for current use.
- HA webhook-only external exposure enables mobile notification actions without exposing the dashboard or API.

## New Secrets / Variables

None.

## Architecture / global.env Updates Required

None.
