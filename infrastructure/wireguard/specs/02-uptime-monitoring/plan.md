# 02 WireGuard Uptime Monitoring

**Status:** IN PROGRESS  
**Date:** September 2026

## 🎯 Goal

Monitor the WireGuard container and `wg0` interface health on the NAS from Uptime Kuma (running on the Pi) without joining the Pi to WireGuard as a peer.

## 🏗️ Architecture

```
[NAS]
  ├── Cron (/etc/cron.d/wireguard-uptime) runs every 5 minutes
  ├── Script (/home/grimur/homelab/infrastructure/wireguard/scripts/uptime-push.sh)
  │     ├── Checks `docker inspect` (container running)
  │     ├── Checks `docker exec wireguard wg show wg0` (interface active)
  │     └── Reads push secret from /root/.uptime-kuma-push-wireguard
  └── Pushes HTTP GET -> [Pi: Uptime Kuma] (Heartbeat interval: 360s / 6m)
```

## 🛠️ Implementation Steps

### 1. NAS Script
- Created `infrastructure/wireguard/scripts/uptime-push.sh` (git-tracked, `chmod +x`).
- Verifies container status and `wg0` interface.
- Loads secret token securely from `/root/.uptime-kuma-push-wireguard` (or `infrastructure/wireguard/.env`).

### 2. Host Cron Setup (NAS)
Create `/etc/cron.d/wireguard-uptime` on the NAS:
```bash
*/5 * * * * root /home/grimur/homelab/infrastructure/wireguard/scripts/uptime-push.sh >/dev/null 2>&1
```

### 3. Secret Configuration (NAS)
Store the secret push webhook URL:
```bash
echo "<UPTIME_KUMA_PUSH_URL>" > /root/.uptime-kuma-push-wireguard
chmod 600 /root/.uptime-kuma-push-wireguard
```

### 4. Uptime Kuma Configuration (Pi)
- **Name:** `WireGuard (Container)`
- **Type:** `Push`
- **Heartbeat Interval:** `360s` (6 minutes)
- **Retries:** 1

## 🔄 Rollback Steps

1. Delete `/etc/cron.d/wireguard-uptime` from the NAS.
2. Remove `/root/.uptime-kuma-push-wireguard`.
3. Delete the push monitor from Uptime Kuma.

