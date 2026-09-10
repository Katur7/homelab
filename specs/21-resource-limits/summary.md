# Spec 21: Docker Resource Limits — Summary

## What Changed

Added `deploy.resources.limits` (memory + CPU) to all 37 running containers across 19 compose files. Two-tier approach:

**Critical services (4x headroom):** traefik, authelia, pihole, cloudflared, wireguard, homeassistant — generous ceilings so they almost never OOM, but still protected against unbounded leaks.

**Standard services (2x headroom):** everything else — enough for normal spikes, fast recovery via `restart: unless-stopped` if an OOM does occur.

All memory limits are powers of 2 (MB).

## Why

- NAS (AMD E-350, 7.4GB RAM) was under memory pressure: 413MB swap at idle
- 37 containers with no limits meant any container could balloon unchecked
- Home Assistant alone was consuming 629MB with no ceiling
- Without limits, kernel OOM killer picks victims unpredictably

## Deviation from Plan

- `immich_server` bumped from 512M to **1024M** during rollout — post-restart usage immediately hit 93% of the 512M limit. 297MB idle sample was misleading; actual working set is ~480MB.

## New Secrets/Variables

None.

## ARCHITECTURE.md Update

Not required — resource limits are implementation detail within each compose file.

## global.env Update

Not required.
