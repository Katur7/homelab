# Milestone 10: Immich Remote Machine Learning (Pi 4)

**Date:** 2026-03-31
**Status:** In Progress

## Problem

The Immich `immich-machine-learning` container (v2.6.1) crashes on the NAS with exit code 132 (SIGILL).

**Root cause:** Since Immich v2.6, NumPy 2.4 requires the x86-64-v2 microarchitecture baseline (SSE4.1, SSE4.2, POPCNT). The NAS CPU (AMD E-350, Bobcat, ~2011) only has SSE4a — an AMD-specific extension that is entirely distinct from SSE4.1/4.2. The E-350 is below the x86-64-v2 baseline, so any x86-64-v2-compiled binary crashes immediately with SIGILL.

This is not a configuration error, corruption, or AVX issue. The hardware is architecturally incompatible with the v2.6+ ML image on amd64.

**Reference:** [immich-app/immich#27127](https://github.com/immich-app/immich/issues/27127)

## Solution

Offload the ML container to the Raspberry Pi 4 (ARM64, Cortex-A72). ARM64 has no equivalent versioned baseline problem — the Pi 4 meets all requirements for the arm64 Immich ML image. The Immich server supports a remote ML URL natively via `IMMICH_MACHINE_LEARNING_URL`.

**Pi 4 RAM budget:**
- OS + PiHole + Nebula-Sync + UptimeKuma: ~700MB–1GB
- Immich ML models (CLIP + facial recognition): ~1–2GB
- Total on 4GB: comfortable headroom

## Steps

### 1. Create Pi ML service
- Add `pi/services/immich-ml/compose.yaml`
- Use `ghcr.io/immich-app/immich-machine-learning:v2.6.1` (arm64 image is the same tag)
- Expose port 3003
- Mount a named volume for model cache
- No Traefik — direct LAN access only

### 2. Update NAS Immich compose
- Remove the `immich-machine-learning` service and its `model-cache` volume from `services/immich/compose.yaml`
- Add `IMMICH_MACHINE_LEARNING_URL=http://192.168.86.26:3003` to `services/immich/vars.env`

### 3. Deploy to Pi
```bash
ssh grimur@192.168.86.26
cd ~/homelab && git pull
cd pi/services/immich-ml
docker compose up -d
```

### 4. Restart Immich server on NAS
```bash
cd services/immich && docker compose up -d
```

### 5. Validate
- Check ML container is healthy on Pi: `docker ps`
- Check Immich server logs — should show successful ML connection
- Verify Smart Search works in the Immich UI
- Confirm no ML container on NAS

## Impact on Other Services

None. Change is fully contained to Immich stack and Pi host.

## Rollback

1. Remove `IMMICH_MACHINE_LEARNING_URL` from `vars.env`
2. Restore `immich-machine-learning` service to NAS compose (note: will crash-loop on v2.6+ — only viable if downgrading Immich)
3. Alternatively: disable ML entirely via Immich Admin UI → Settings → Machine Learning Settings

## New Secrets / Variables

| Variable | File | Purpose |
|----------|------|---------|
| `IMMICH_MACHINE_LEARNING_URL` | `services/immich/vars.env` | Points Immich server at remote ML on Pi |

## Architecture / global.env Updates Required

- `ARCHITECTURE.md` should note that Immich ML runs on the Pi, not the NAS
