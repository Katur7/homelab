# Raspberry Pi — Secondary Host

## Role

Secondary/backup host on the LAN. Runs DNS failover (PiHole), config sync (Nebula-Sync),
and uptime monitoring (UptimeKuma).

## Host Details

| Property | Value |
|----------|-------|
| Hostname | `raspberrypi` |
| LAN IP | `192.168.86.26` (static DHCP reservation) |
| OS | Raspberry Pi OS Lite (Bookworm) |
| Access | SSH key-only — `ssh grimur@192.168.86.26` |

## Services

| Service | Port | URL |
|---------|------|-----|
| PiHole (backup DNS) | 53, 80 | `http://192.168.86.26/admin` |
| UptimeKuma | 3001 | `http://192.168.86.26:3001` |

Nebula-Sync has no web UI — runs as a sidecar to PiHole.
Docker image updates are handled by a weekly cron job (`pi/scripts/update-containers.sh`).

## No Traefik

Services are accessed directly by port on the LAN IP. No reverse proxy on this host.

## Deployment

```bash
# PiHole + Nebula-Sync
cd ~/homelab/pi/services/pihole
docker compose up -d

# UptimeKuma
cd ~/homelab/pi/services/uptime-kuma
docker compose up -d
```

## Repo Layout

```
pi/
  global.env          # Pi-wide vars (TZ, PUID/PGID)
  services/
    pihole/           # PiHole + Nebula-Sync (same stack)
    uptime-kuma/
```
