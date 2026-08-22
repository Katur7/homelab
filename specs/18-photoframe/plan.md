# Milestone 18: Register Photoframe Stack on Pi

## Goal

Register the photoframe service — an HTTP server on the Pi serving a static PNG to an ESP32-S3 photo frame — in the homelab repo. The stack itself lives in a separate repo ([photoframe-server](https://github.com/Katur7/photoframe-server)) cloned at `~/photoframe-server` on the Pi; this milestone adds DNS, documentation, and the directory entry.

## Context

- Port: **8088** on `192.168.86.26`
- URL: `http://photoframe.internal.pippinn.me:8088/current.png`
- No Traefik, no TLS, no proxy — the ESP32 fetches direct HTTP once per day
- The compose file lives in the photoframe-server repo (it uses `build: .`) — duplicating it here would cause drift

## Sub-milestones

### 18.1 — DNS override (do first)

The wildcard `address=/.internal.pippinn.me/192.168.86.17` currently resolves `photoframe.internal.pippinn.me` to the NAS (wrong host). Add a more-specific `address=` line to override it:

```
address=/photoframe.internal.pippinn.me/192.168.86.26
```

dnsmasq takes the longest matching domain, so this wins over the wildcard.

**Both files must be edited** — `SYNC_CONFIG_MISC=false` in nebula-sync means this env var does not sync:

| File | Current value | New value |
|------|--------------|-----------|
| `infrastructure/dns/vars.env` | `address=/.internal.pippinn.me/192.168.86.17` | `address=/.internal.pippinn.me/192.168.86.17;address=/photoframe.internal.pippinn.me/192.168.86.26` |
| `pi/services/pihole/vars.env` | `address=/.internal.pippinn.me/192.168.86.17` | `address=/.internal.pippinn.me/192.168.86.17;address=/photoframe.internal.pippinn.me/192.168.86.26` |

**Separator:** Confirm `;` is the correct array separator for `FTLCONF_misc_dnsmasq_lines` by checking `pihole-FTL --config misc.dnsmasq_lines` after restart — it should show two entries.

**Verification** — all three must answer `192.168.86.26`:
```bash
dig +short photoframe.internal.pippinn.me @192.168.86.27   # NAS PiHole
dig +short photoframe.internal.pippinn.me @192.168.86.26   # Pi PiHole
dig +short photoframe.internal.pippinn.me                  # default resolver
```

**Note:** Do NOT verify from the Pi host itself — its `/etc/resolv.conf` points at `1.1.1.1`, so it cannot resolve any `*.internal.pippinn.me` name. Use `dig @192.168.86.26` (queries the PiHole container directly) instead.

### 18.2 — Pi service directory

Create `pi/services/photoframe/README.md` (documentation only — no compose.yaml in this repo).

Contents: stack identity, port 8088, URL, pointer to `~/photoframe-server`, deploy/rollback commands, explicit note that there is no compose file in this repo and why.

### 18.3 — Update pi/README.md

- **Services table:** add photoframe — port 8088, URL `http://photoframe.internal.pippinn.me:8088/current.png`
- **Repo Layout:** add `photoframe/` entry with note that the directory is documentation only

### 18.4 — update-containers.sh comment

Add a comment to `pi/scripts/update-containers.sh` explaining why photoframe is excluded from `STACKS`: the script does `docker compose pull` but the photoframe image is locally built (`build: .`), so there is no upstream to pull. Updating means rebuilding from its own git remote.

## Not in scope

- **No Traefik route** — direct port on LAN IP per Pi's "no reverse proxy" policy
- **No `.env` or secrets** — nothing secret until a future Immich integration
- **No changes to `STACKS` array** — photoframe is excluded by design
- **TZ mismatch** (`pi/global.env` says `Europe/Stockholm`, Pi host `/etc/timezone` says `Europe/London`) — pre-existing, not caused by this task. The photoframe container declares `TZ=Europe/Stockholm` explicitly so it is correct regardless. Flagged for the user to decide separately.
- **Sync canary** (`sync-verify.internal.pippinn.me`) — the wildcard makes this monitor unfalsifiable. Worth its own item but not blocking.

## Files Changed

| File | Change |
|------|--------|
| `infrastructure/dns/vars.env` | Append photoframe `address=` override to dnsmasq lines |
| `pi/services/pihole/vars.env` | Same override |
| `pi/services/photoframe/README.md` | New — documentation-only service entry |
| `pi/README.md` | Add photoframe to services table and repo layout |
| `pi/scripts/update-containers.sh` | Add exclusion comment |
| `specs/18-photoframe/plan.md` | This file |
| `specs/18-photoframe/summary.md` | Post-completion |

## Rollback

- Revert the `FTLCONF_misc_dnsmasq_lines` lines in both vars.env files
- Restart both PiHole containers
- Delete `pi/services/photoframe/` directory
- Revert `pi/README.md` and `update-containers.sh`

## Impact on Other Services

- **PiHole (both instances):** restart required to pick up the new dnsmasq line
- **All other services:** no impact — the override is specific to `photoframe.internal.pippinn.me`
