# UptimeKuma — Monitor Configuration

All config lives in `kuma.db` (SQLite, not git-tracked). This file is the rebuild reference.
To query current state: `docker exec uptime-kuma sqlite3 /app/data/kuma.db "SELECT name, type, url, hostname, port, interval FROM monitor WHERE active=1;"`

## Monitors

### Group: PiHole

| Name | Type | Target | DNS Server | Port | Interval |
|------|------|--------|------------|------|----------|
| PiHole-NAS | DNS | `google.com` | `192.168.86.27` | 53 | 180s |
| PiHole-Pi | DNS | `google.com` | `192.168.86.26` | 53 | 180s |

### Other

| Name | Type | URL | Interval |
|------|------|-----|----------|
| Hello - Cloudflare tunnel | HTTP | `https://hello.pippinn.me` | 300s |

Monitors the Cloudflare tunnel and Traefik routing on the NAS from the Pi's perspective.

## Rebuild Steps

1. Deploy UptimeKuma: `cd pi/services/uptime-kuma && docker compose up -d`
2. Open `http://192.168.86.26:3001` and complete first-run setup
3. Re-create monitors manually using the table above
4. Verify all monitors are green
