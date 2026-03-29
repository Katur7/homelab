# UptimeKuma — Monitor Configuration

All config lives in `kuma.db` (SQLite, not git-tracked). This file is the rebuild reference.
To query current state: `docker exec uptime-kuma sqlite3 /app/data/kuma.db "SELECT name, type, url, hostname, port, interval FROM monitor WHERE active=1;"`

## Monitors

### Group: PiHole

| Name | Type | Target | DNS Server | Port | Interval |
|------|------|--------|------------|------|----------|
| PiHole-NAS | DNS | `google.com` | `192.168.86.27` | 53 | 180s |
| PiHole-Pi | DNS | `google.com` | `192.168.86.26` | 53 | 180s |
| PiHole-Pi-Sync | DNS | `sync-verify.internal.pippinn.me` | `192.168.86.26` | 53 | 180s |

**PiHole-Pi-Sync** verifies that Nebula-Sync completed at least one successful sync —
if `sync-verify.internal.pippinn.me` never resolves on the Pi, sync has never worked.

> **Limitation:** PiHole does not delete records when sync stops. Once the canary record
> is synced, it persists on the Pi indefinitely. This monitor will not detect ongoing sync
> failure after the first successful run. Use a Docker container monitor on `nebula-sync`
> to catch crashes. Silent auth failures (wrong password) have no automated detection —
> they only occur if the PiHole password is changed without updating `.env`.

> The canary record `sync-verify.internal.pippinn.me` must exist on the NAS PiHole pointing
> to any valid IP (e.g. `192.168.86.26`). Do not delete it.

### Other

| Name | Type | URL | Interval |
|------|------|-----|----------|
| Hello - Cloudflare tunnel | HTTP | `https://hello.pippinn.me` | 300s |

Monitors the Cloudflare tunnel and Traefik routing on the NAS from the Pi's perspective.

## Rebuild Steps

1. Deploy UptimeKuma: `cd pi/services/uptime-kuma && docker compose up -d`
2. Open `http://192.168.86.26:3001` and complete first-run setup
3. Re-create monitors manually using the table above
4. Verify `sync-verify.internal.pippinn.me` exists on the NAS PiHole before adding PiHole-Pi-Sync
