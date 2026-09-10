# Milestone 16: On-Demand Service Scaling via Sablier

## Goal
Stop idle LinguaCafe containers after 60 min. On next request, show a dynamic loading page while they cold-start, then forward traffic. Repeatable pattern for future services.

## Key Decisions
| Decision | Choice |
|---|---|
| Plugin | `github.com/sablierapp/sablier v1.11.2` (not the archived `acouvreur` fork) |
| Mode | Dynamic (loading page, not a blocking hang) |
| Idle timeout | 60 minutes |
| Stack placement | Gateway stack (needs `socket_proxy` + `traefik_internal`) |
| Docker socket access | Extend existing socket-proxy with `SP_ALLOW_POST`, regex-locked to exact container names |
| Containers managed | `linguacafe-webserver`, `linguacafe-python-service`, `linguacafe-database` |

## Known Risk: depends_on bypass
Sablier uses `docker start` directly — compose `depends_on` is ignored. Webserver will crash-loop briefly until MySQL is healthy. Mitigated by `restart: unless-stopped` (already set) and a healthcheck on the webserver with `start_period: 60s`.

## Files Changed
1. `infrastructure/gateway/config/traefik.yml` — add `sablierapp/sablier` to `experimental.plugins`
2. `infrastructure/gateway/compose.yaml` — add Sablier service; add `SP_ALLOW_POST` to socket-proxy (locked to 3 container names, `start`/`stop` only)
3. `infrastructure/gateway/config/dynamic/sablier.yml` — new file; defines `sablier-linguacafe` middleware
4. `services/linguacafe/compose.yaml` — add healthcheck to webserver; add `sablier-linguacafe@file` middleware to router

## Rollback
Reverse the four file changes and recreate both stacks. No secrets or volumes involved.

---

# Extension: Calibre-Web + Journiv

## Goal
Apply the same on-demand scaling pattern to two more rarely-used services.

## Services Added

### Calibre-Web (1 container)
| Item | Value |
|---|---|
| Container | `calibre-web` |
| Route | `ebooks.internal.pippinn.me` (websecure) |
| Idle timeout | 1h |
| Notes | Add healthcheck (port 8083). Single container — simplest case. |

### Journiv (4 containers)
| Item | Value |
|---|---|
| Containers | `journiv-app`, `journiv-celery-worker`, `journiv-celery-beat`, `journiv-valkey` |
| Internal route | `dagbok.pippinn.me` (websecure) |
| Tunnel route | `dagbok.pippinn.me` (tunnel, authelia-auth first then sablier) |
| Idle timeout | 1h |
| Notes | Auth middleware before Sablier on tunnel — prevents unauthenticated wake triggers. |

## Files Changed
1. `infrastructure/gateway/compose.yaml` — expand `SP_ALLOW_POST` regex with 5 new container names
2. `infrastructure/gateway/config/dynamic/sablier.yml` — add routers/services/middlewares for both services
3. `services/calibre-web/compose.yaml` — remove Traefik labels, add healthcheck
4. `services/journiv/compose.yaml` — remove Traefik labels from `journiv-app`

## Rollback
Revert the four files and recreate gateway + both service stacks.
