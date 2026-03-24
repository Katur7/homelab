# Milestone 05 Summary: Remaining Infrastructure Services

**Date:** 2026-03-24
**Status:** `PARTIALLY COMPLETE` — WUD ✅ WireGuard ✅ Tailscale ⏳ (pending new auth key)
**Author:** grimur & NAS Helper (AI)

## 📝 Executive Summary

Migrated WUD (What's Up Docker) and WireGuard from OMV-managed compose files into the
GitOps-controlled `infrastructure/` directory. Tailscale was set up but is currently
stopped — the OMV auth key was a one-time key that was already consumed; a new key is
needed from the Tailscale admin console before it can be started.

## 🛠️ What We Did

1. **Created `infrastructure/wud/`** — What's Up Docker:
   - `getwud/wud:8.2.2` (pinned from running container)
   - GitHub PAT moved from hardcoded compose value → `.env`
   - Traefik label `${TRAEFIK_URL}` variable replaced with hardcoded `update.internal.pippinn.me`

2. **Created `infrastructure/tailscale/`** — Tailscale mesh VPN:
   - `tailscale/tailscale:stable`
   - `TS_AUTHKEY` moved to `.env`
   - State volume migrated from `/appdata/tailscale/state/` → `./state/` (gitignored)
   - **Currently stopped** — auth key expired; see Known Issues below

3. **Created `infrastructure/wireguard/`** — WireGuard road-warrior VPN:
   - `ghcr.io/linuxserver/wireguard:1.0.20250521` (pinned from running container)
   - Volume migrated from `/appdata/wireguard/config` → `./config/` (gitignored)
   - Started cleanly: `No changes to parameters. Existing configs are used.`
   - All 4 peer configs preserved — no redistribution needed

4. **Updated `.gitignore`**:
   - `/infrastructure/tailscale/state/` — binary runtime state
   - `/infrastructure/wireguard/config/` — server + peer private keys

## ⚙️ Final Directory Structure

```
infrastructure/
  wud/
    compose.yaml        ← whatsupdocker container
    vars.env            ← WUD_REGISTRY_LSCR_USERNAME, WUD_WATCHER_*
    .env                ← git-ignored: WUD_REGISTRY_LSCR_PRIVATE_TOKEN
  tailscale/
    compose.yaml        ← tailscale container (currently stopped)
    vars.env            ← TS_STATE_DIR, TS_USERSPACE
    .env                ← git-ignored: TS_AUTHKEY (needs replacement)
    state/              ← git-ignored: binary runtime state
  wireguard/
    compose.yaml        ← wireguard container
    vars.env            ← SERVERURL, SERVERPORT, PEERS, PEERDNS, LOG_CONFS
    config/             ← git-ignored: server + peer keys
```

## ⚓ Key Decisions

- **WUD image pinned to `8.2.2`** — OMV used untagged `getwud/wud`; pinned to running version.
- **WireGuard image pinned to `1.0.20250521`** — OMV used `:latest`; pinned to running version.
- **Tailscale `:stable` kept** — no versioned release tags available for this image.
- **WireGuard config gitignored** — entire `./config/` directory contains private keys.
  Existing config copied verbatim; no peer redistribution required.
- **Tailscale state gitignored** — binary state file; not human-readable or useful in git.

## 🆕 New Secrets / Variables Created

No new secrets. Existing values migrated from OMV compose files:

| Variable | Location | Purpose |
|----------|----------|---------|
| `WUD_REGISTRY_LSCR_PRIVATE_TOKEN` | `infrastructure/wud/.env` | GitHub PAT for LSCR registry |
| `TS_AUTHKEY` | `infrastructure/tailscale/.env` | Tailscale auth key (expired — needs replacement) |

## 📋 ARCHITECTURE.md Update Required?

No — no new networks or topology changes introduced by this milestone.

## ⚠️ Known Issues & Technical Debt

- **Tailscale auth key expired**: The `TS_AUTHKEY` in `infrastructure/tailscale/.env` is a
  consumed one-time key. To re-enable Tailscale:
  1. Generate a new reusable auth key at `admin.tailscale.com` → Settings → Keys
  2. Update `infrastructure/tailscale/.env`: `TS_AUTHKEY=<new-key>`
  3. `docker compose -f infrastructure/tailscale/compose.yaml up -d`
- **WUD non-semver warnings**: Several containers use non-semver tags (`:stable`, digest
  pins). WUD cannot track updates for these without digest watching enabled. Pre-existing
  issue, not introduced by this migration.
- **WUD `proxy_vikunja-db` regex**: No tags found after filtering — the `wud.tag.include`
  label on that container likely needs updating.

## 🏁 Result

WUD and WireGuard are fully operational under GitOps. Tailscale is defined in Git and
ready to start once a valid auth key is provided. The next logical step is **Milestone 06**
(application service migrations: Immich, Home Assistant, etc.).
