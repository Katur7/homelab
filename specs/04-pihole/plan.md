# Milestone 04: PiHole DNS Infrastructure — Plan

## Context
The NAS PiHole (192.168.86.27) is currently managed by OMV via `/appdata/pihole/pihole.yml`.
Goal: migrate it into `infrastructure/dns/` under GitOps control.

The Pi PiHole (192.168.86.26) stays as-is — it is the replica in nebula-sync.
The NAS PiHole is the **PRIMARY** (source of truth for DNS config).

Source file: `/appdata/pihole/pihole.yml`

---

## What We Know From the Existing OMV Compose

- **Image:** `pihole/pihole:2026.02.0` (keep exactly)
- **Networks:** `pihole_network` (macvlan, `enp4s0`) + `traefik_internal` (external)
- **IPv6** macvlan supported (subnet `2001:9b1:c5c0:7e00::/64`)
- **Volume:** `/appdata/pihole/config/:/etc/pihole/` (single mount — all runtime data)
- **`dnsmasq.d/`** at `/appdata/pihole/dnsmasq.d/` is NOT mounted — it's legacy. The
  wildcard DNS rule `address=/.internal.pippinn.me/192.168.86.17` is already set via
  `FTLCONF_misc_dnsmasq_lines`. No dnsmasq.d mount needed.
- **Traefik labels** on the container (using `traefik_internal` network)
- **Web password** currently hardcoded in OMV compose → move to `.env`

---

## Folder Structure

```
infrastructure/
  dns/
    compose.yaml
    vars.env          ← git-tracked (all FTLCONF_* except password, PIHOLE_UID/GID)
    .env              ← git-ignored (FTLCONF_WEBSERVER_API_PASSWORD)
    config/           ← bind-mounted to /etc/pihole — fully gitignored
```

---

## compose.yaml

```yaml
networks:
  pihole_network:
    name: pihole_network
    driver: macvlan
    driver_opts:
      parent: enp4s0
    enable_ipv6: true
    ipam:
      config:
        - gateway: 192.168.86.1
          subnet: 192.168.86.0/24
        - subnet: 2001:9b1:c5c0:7e00::/64
  traefik_internal:
    external: true

services:
  pihole:
    image: pihole/pihole:2026.02.0
    container_name: pihole
    hostname: pihole
    env_file:
      - ../../global.env
      - vars.env
      - .env
    dns:
      - 127.0.0.1
      - 1.1.1.1
    networks:
      pihole_network:
        ipv4_address: 192.168.86.27
        ipv6_address: 2001:9b1:c5c0:7e00::10
      traefik_internal:
    volumes:
      - ./config:/etc/pihole
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.pihole-internal.entrypoints=websecure"
      - "traefik.http.routers.pihole-internal.rule=Host(`pihole.internal.pippinn.me`)"
      - "traefik.http.services.pihole.loadbalancer.server.port=80"
      - "traefik.docker.network=traefik_internal"
    restart: always
```

**Notes:**
- `PIHOLE_UID/GID` hardcoded in `vars.env` (env_file does not support variable interpolation)
- `pihole_network` defined here (not external) — this stack owns the macvlan definition
- Password injected via `FTLCONF_WEBSERVER_API_PASSWORD` from `.env`

---

## vars.env

```env
PIHOLE_UID=1000
PIHOLE_GID=100
FTLCONF_dns_reply_host_IPv4=192.168.86.27
FTLCONF_dns_upstreams=1.1.1.1
FTLCONF_dns_listeningMode=all
FTLCONF_webserver_port=80
FTLCONF_webserver_interface_theme=default-dark
FTLCONF_webserver_domain=pihole.internal.pippinn.me
FTLCONF_misc_dnsmasq_lines=address=/.internal.pippinn.me/192.168.86.17
```

---

## .gitignore Addition

```
# PiHole — entire config volume is runtime state (gravity.db, pihole.toml, logs, etc.)
/infrastructure/dns/config/
```

---

## routes.yml

No changes needed. The NAS PiHole uses Traefik labels.
The existing `pihole-on-pi` static route stays for the Pi's web UI.

---

## ARCHITECTURE.md Updates

1. Add `pihole_network` (macvlan, `enp4s0`) to network overview
2. Add `infrastructure/dns/` to directory overview
3. Document Traefik entrypoint/middleware reference table

---

## Implementation Steps

### Phase 1: Prep
1. Note current web password from `/appdata/pihole/pihole.yml`
2. Create `specs/04-pihole/` directory

### Phase 2: Create GitOps files
3. Create `infrastructure/dns/compose.yaml`
4. Create `infrastructure/dns/vars.env`
5. Populate `infrastructure/dns/.env` on server: `FTLCONF_WEBSERVER_API_PASSWORD=<password>`
6. Update `.gitignore` — add `/infrastructure/dns/config/`

### Phase 3: Migrate data volume
7. `sudo cp -a /appdata/pihole/config/ infrastructure/dns/config`
8. `sudo chown -R 1000:100 infrastructure/dns/config/`

### Phase 4: Validate
9. `docker compose -f infrastructure/dns/compose.yaml config`

### Phase 5: Cutover
10. Stop OMV pihole stack in OMV UI
11. `docker compose -f infrastructure/dns/compose.yaml up -d`
12. Verify DNS: `docker exec pihole nslookup google.com 127.0.0.1`
13. Verify web UI: `https://pihole.internal.pippinn.me`
14. Verify nebula-sync on Pi still connects to NAS primary
15. Disable OMV stack in OMV UI

### Phase 6: Commit & Document
16. Update `ARCHITECTURE.md`
17. Git commit
18. Create `specs/04-pihole/summary.md`

---

## Risks

- **`pihole_network` name conflict**: OMV currently owns the `pihole_network` macvlan.
  Must stop OMV stack first; new stack then recreates the network cleanly.
- **IPv6 macvlan**: Google WiFi doesn't support the link-local gateway for IPv6 (no
  gateway in IPv6 block). Same limitation preserved as-is from the OMV compose.
- **nebula-sync reconnect**: After cutover, nebula-sync on the Pi will reconnect to the
  same IP (192.168.86.27) — should be seamless.
- **Config volume ownership**: `sudo cp -a` preserves original ownership. Verify and
  chown if needed.
- **env_file interpolation**: Docker Compose env_file does NOT expand `${VAR}` references.
  PIHOLE_UID/GID are hardcoded in vars.env; password is resolved via `.env` auto-load.

---

## Rollback Plan

1. `docker compose -f infrastructure/dns/compose.yaml down`
2. Re-enable OMV pihole stack in OMV UI
3. DNS restored to 192.168.86.27 — no client changes needed
