# Spec 21: Docker Resource Limits (CPU + Memory)

## Problem

The NAS (AMD E-350, 7.4GB RAM, 2 cores) is under memory pressure:
- 413MB swap in use at idle
- 37 running containers with no resource limits (except journiv + flatnotes)
- Home Assistant alone consumes 629MB uncapped
- Any container can balloon, pushing others into swap or triggering unpredictable OOM kills

## Goal

Add `deploy.resources.limits` (memory + CPU) to all services. This:
- Caps each container so a runaway process kills only itself
- Reduces swap pressure by preventing aggregate overcommit
- Makes memory behaviour predictable and observable via `docker stats`

## Design: Two-Tier Limits

**Critical services** get ~4x headroom — they almost never hit their ceiling but are still protected against unbounded leaks. An OOM-kill on these has outsized blast radius (all routing, DNS, external access, or automations down).

**Standard services** get ~2x headroom — enough for normal spikes, and `restart: unless-stopped` means a rare OOM-kill recovers in seconds.

All memory values are powers of 2 (MB).

### Critical Services (4x headroom)

| Compose file | Service | Current Mem | Mem Limit | CPU Limit | Why critical |
|---|---|---|---|---|---|
| home-assistant | homeassistant | 629MB | 2048M | 1.5 | Automations, smart home |
| gateway | reverse-proxy (traefik) | 104MB | 512M | 1.0 | All web routing |
| gateway | authelia | 66MB | 256M | 0.5 | Auth for all external services |
| dns | pihole | 84MB | 256M | 0.5 | Network-wide DNS |
| cloudflare | cloudflared | 30MB | 128M | 0.25 | External access tunnel |
| wireguard | wireguard | 85MB | 256M | 0.5 | VPN access |

### Standard Services — NAS (`services/`)

| Compose file | Service | Current Mem | Mem Limit | CPU Limit |
|---|---|---|---|---|
| home-assistant | matter-server | 131MB | 256M | 0.5 |
| home-assistant | ord_dagsins | 58MB | 128M | 0.25 |
| immich | immich-server | 297MB | 1024M | 1.0 |
| immich | database | 56MB | 256M | 0.5 |
| immich | redis | 11MB | 64M | 0.25 |
| starr | sonarr | 80MB | 256M | 0.5 |
| starr | radarr | 67MB | 256M | 0.5 |
| starr | prowlarr | 82MB | 256M | 0.5 |
| starr | qbittorrent | 52MB | 256M | 1.0 |
| calibre-web | calibre-web | 199MB | 512M | 1.0 |
| audiobookshelf | audiobookshelf | 79MB | 256M | 0.5 |
| vikunja | vikunja | 59MB | 128M | 0.5 |
| vikunja | db | 30MB | 128M | 0.25 |
| plex | plex | 95MB | 512M | 1.5 |
| syncthing | syncthing | 83MB | 256M | 1.0 |
| flatnotes | flatnotes | 53MB | 128M | 0.25 |
| it-tools | tools | 3MB | 32M | 0.1 |
| hello-world | hello | 1MB | 16M | 0.1 |
| beszel-agent | beszel-agent | 8MB | 32M | 0.1 |

### Standard Services — Infrastructure (`infrastructure/`)

| Compose file | Service | Current Mem | Mem Limit | CPU Limit |
|---|---|---|---|---|
| gateway | crowdsec | 154MB | 256M | 0.5 |
| gateway | redis | 23MB | 64M | 0.25 |
| gateway | sablier | 44MB | 128M | 0.25 |
| gateway | socket-proxy | 9MB | 32M | 0.1 |
| cloudflare | cloudflare-ddns | 4MB | 32M | 0.1 |
| tailscale | tailscale | 96MB | 256M | 0.5 |
| wud | whatsupdocker | 113MB | 256M | 0.5 |
| wud | autoupdater | 20MB | 64M | 0.25 |

### Already limited (journiv) — no changes

| Service | Existing Limit |
|---|---|
| journiv app | 2048M / 2.0 CPU |
| journiv celery-worker | 1024M / 1.0 CPU |
| journiv celery-beat | 1024M / 1.0 CPU |
| journiv admin-cli | 1024M / 1.0 CPU |
| journiv valkey | (none — add 64M / 0.25 CPU) |

### Not modified

| Service | Reason |
|---|---|
| linguacafe (all) | Containers removed, service not deployed |

## Aggregate budget

Total proposed limits: ~10.3GB (including existing journiv limits).
Actual usage at idle: ~3.2GB.
System RAM: 7.4GB.

Limits are ceilings, not reservations — Docker doesn't pre-allocate. The sum can exceed physical RAM safely as long as real usage stays under. If multiple services spike simultaneously, Docker OOM-kills the one that hit its limit, not a random process.

## Implementation

1. Add `deploy.resources.limits.memory` and `deploy.resources.limits.cpus` to each service in its `compose.yaml`
2. Update flatnotes limit from current value to stay consistent
3. Add limits to journiv valkey (only journiv service without limits)
4. Validate each compose file with `docker compose config`
5. Rolling restart: `docker compose up -d` per stack
6. Monitor via `docker stats` and Beszel for OOM events

## Constraints

- `homeassistant` uses `network_mode: host` + `privileged: true` — resource limits still work with cgroups v2 (OMV Debian 12 uses cgroupv2 by default)
- `wireguard` uses `cap_add` / `sysctls` — limits compatible
- `pihole` uses macvlan — limits compatible

## Rollback

Remove the `deploy.resources` blocks and `docker compose up -d`. No data impact.

## Risks

- A limit set too low causes OOM-kill → container restarts. Mitigated by ~2x headroom (standard) or ~4x headroom (critical).
- Home Assistant at 629MB with 2048M limit has the most absolute headroom of any service.
- Monitor all services post-deployment; adjust limits if any service shows repeated OOM-kills.
