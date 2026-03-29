# Milestone 07.3 Summary: Tailscale Activation

**Date:** 2026-03-29
**Status:** `COMPLETE`

---

## What Was Changed

| File | Change |
|------|--------|
| `infrastructure/tailscale/compose.yaml` | Pinned image `tailscale/tailscale:stable` → `v1.94.2` |
| `infrastructure/tailscale/.env` | Removed stale `TS_AUTHKEY` — replaced with commented-out placeholder and explanation |

## Why

The container had never been started under GitOps (no prior `docker compose up -d`).
A stale auth key was present in `.env` from a prior manual run on 2026-03-24. The
entrypoint passes `TS_AUTHKEY` to `tailscale up` on every start — an expired key would
cause authentication failure even though valid node state existed in `state/tailscaled.state`.

Removing the key allows the container to reconnect using the existing identity in
`tailscaled.state` without triggering a re-authentication flow.

## Outcome

Container started cleanly. Node came online immediately:

```
100.107.106.77  pippinn  grimurk@  linux  -
```

No new auth key required — existing state was valid (last clean shutdown 2026-03-24, 5 days ago).

## No Architecture / global.env Changes Required

Tailscale IP (`100.107.106.77`) and hostname (`pippinn`) are unchanged from previous run.

## Note on TS_AUTHKEY

`.env` now has the key commented out. If the node ever needs to re-authenticate
(e.g. after being removed from the Tailscale admin console), uncomment and set a new
reusable key, then `docker compose up -d`. For long-term robustness on paid plans,
consider switching to OAuth client credentials which never expire.
