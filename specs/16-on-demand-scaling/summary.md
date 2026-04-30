# Milestone 16: Summary

## What Changed
- Added Sablier v1.11.2 daemon to gateway stack (Docker provider via socket-proxy)
- Added `sablierapp/sablier-traefik-plugin v1.1.0` to Traefik's experimental plugins
- Extended socket-proxy with `SP_ALLOW_POST` locked to `start`/`stop` on the 3 LinguaCafe containers only
- Defined LinguaCafe router + service + Sablier middleware in file provider (`dynamic/sablier.yml`)
- Added healthcheck (`curl -f http://localhost/`, `start_period: 60s`) to `linguacafe-webserver`
- Removed Traefik routing labels from `linguacafe-webserver` (route now owned by file provider)

## Why
LinguaCafe is resource-heavy and rarely used. Containers are now stopped after 60 min of inactivity and cold-started on demand with a dynamic loading page.

## Key Lessons / Deviations from Plan
1. **Plugin repo split**: `github.com/sablierapp/sablier` no longer carries the `.traefik.yml` manifest. The Traefik plugin moved to `github.com/sablierapp/sablier-traefik-plugin`. Version `v1.1.0`.
2. **Docker image tag**: no `v` prefix — `sablierapp/sablier:1.11.2`.
3. **`--provider.docker.host` flag removed**: v1.11.x uses `DOCKER_HOST` env var instead.
4. **Route must live in file provider**: Docker label-based routes disappear when containers stop. The router must be defined statically in the file provider so Sablier can intercept requests even when containers are down.

## New Secrets / Variables
None.

## ARCHITECTURE.md / global.env Updates Needed
None required. Sablier uses existing `traefik_internal` and `socket_proxy` networks.

## Future Extensibility
To add a new service (e.g. Calibre-Web):
1. Add its container names to the `SP_ALLOW_POST` regex in socket-proxy
2. Add a new router/service/middleware block in `sablier.yml`
3. Remove Traefik routing labels from the service container (or set `traefik.enable=false`)
