# Milestone 25: Summary

## What Changed
- **Gateway Socket Proxy (`infrastructure/gateway/compose.yaml`):**
  - Updated `SP_ALLOW_GET` to include `info` and `_ping` (`(/v1\..{1,2})?/(version|info|_ping|containers/.*|networks|nodes|services|system/df|events.*|images/.*)`).
  - Generalized `SP_ALLOW_POST` to `(/v1\..{1,2})?/containers/([a-zA-Z0-9_.-]+)/(start|stop|restart)` so Dozzle UI container actions and Sablier on-demand container scaling can operate without full Docker API permissions.
- **NAS Dozzle (`services/dozzle/compose.yaml`):**
  - Removed direct `/var/run/docker.sock:/var/run/docker.sock` volume mount.
  - Attached to external network `socket_proxy`.
  - Configured `DOCKER_HOST: tcp://socket-proxy:2375`.
  - Configured `DOZZLE_HOSTNAME: pippinn` to match host naming convention alongside `pihole-pi`.
- **Documentation:**
  - Created [`specs/25-dozzle-socket-proxy/plan.md`](plan.md).
  - Updated [`ARCHITECTURE.md`](../../ARCHITECTURE.md) to record the socket-proxy hardening for Dozzle on NAS.

## Why
Direct `/var/run/docker.sock` mounts give containers root-equivalent capabilities on the Docker host. Proxying Dozzle via `wollomatic/socket-proxy` restricts Dozzle to container log streaming, stats, and non-destructive lifecycle actions (`start`, `stop`, `restart`), completely preventing container creation, deletion, arbitrary exec, volume mount modifications, or privilege escalation.

## Key Lessons / Deviations from Plan
None. The architecture mirrors the proven setup implemented for Dozzle Agent on Raspberry Pi in Milestone 24.

## Deployment Commands (NAS)
```bash
# 1. Update gateway socket-proxy with expanded rules
cd ~/homelab/infrastructure/gateway
docker compose up -d socket-proxy

# 2. Recreate Dozzle to drop direct socket mount and connect to socket-proxy
cd ~/homelab/services/dozzle
docker compose up -d --force-recreate
```
