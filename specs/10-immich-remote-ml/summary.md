# Milestone 10 Summary: Immich Remote Machine Learning (Pi 4)

**Date:** 2026-03-31
**Status:** Complete

## What Was Done

Offloaded the Immich machine learning container from the NAS to the Raspberry Pi 4.

## Why

The NAS CPU (AMD E-350, Bobcat, ~2011) is below the x86-64-v2 microarchitecture baseline. Since Immich v2.6, NumPy 2.4 requires SSE4.1, SSE4.2, and POPCNT — none of which the E-350 has. The ML container crashed immediately on startup with exit code 132 (SIGILL). This is a hardware incompatibility, not a configuration issue.

The Raspberry Pi 4 (ARM64, Cortex-A72) is unaffected — the arm64 image has no equivalent baseline requirement.

## Changes

| File | Change |
|------|--------|
| `services/immich/compose.yaml` | Removed `immich-machine-learning` service and `model-cache` volume; added `shm_size: 128mb` to database; bumped redis to valkey:9 |
| `services/immich/vars.env` | Added `IMMICH_MACHINE_LEARNING_URL=http://192.168.86.26:3003` |
| `pi/services/immich-ml/compose.yaml` | New — runs ML container on Pi, exposes port 3003 |

## Validation

- Pi ML container responds to `/ping` (returns `pong`)
- Immich server log confirmed: `Machine learning server became healthy (http://192.168.86.26:3003)`
- Smart Search job run successfully — semantic search returns correct results

## Notes

- The GPU discovery warning on the Pi (`Failed to open file: /sys/class/drm/card1/device/vendor`) is benign — container falls back to CPU inference as expected
- Smart Search and Face Detection job queues start at 0 — run them manually from Administration → Jobs after first deploy to build embeddings for existing photos

## New Secrets / Variables

| Variable | File | Purpose |
|----------|------|---------|
| `IMMICH_MACHINE_LEARNING_URL` | `services/immich/vars.env` | Points Immich server at remote ML on Pi |

## Architecture / global.env Updates Required

`ARCHITECTURE.md` should be updated to note that Immich ML runs on the Pi (192.168.86.26:3003), not the NAS.
