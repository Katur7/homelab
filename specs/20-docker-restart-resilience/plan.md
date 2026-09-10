# Milestone 20: Docker Engine Restart Resilience

## Problem

After a Docker engine update (via `apt upgrade` or OMV), some containers fail to
restart with **exit code 128** due to a containerd bug: stale task references survive
the engine restart. `docker restart` cannot clear them — only `docker rm -f` followed
by `docker compose up -d` recovers the service.

**Observed incident (2026-09-09):** plex, syncthing, and ord_dagsins all hit this after
an engine update. Manual intervention was required for each.

## Root Cause

containerd maintains task state independently of Docker's container metadata. When the
Docker daemon stops and restarts (as happens during a package upgrade), containerd may
retain stale references to tasks that no longer exist. When Docker tries to start the
container via its restart policy, containerd rejects it because a task with that ID
"already exists" — but the task is a ghost. Exit code 128.

## Solution

A **systemd service unit** (`homelab-containers.service`) that cleanly removes
containers before Docker shuts down, and restores only the previously-active stacks
when Docker starts again. Existing Docker restart policies (`unless-stopped` / `always`)
are preserved and continue to handle container crashes during normal operation.

### Design: state-aware stop/start

**Key constraint:** `docker compose down` removes containers entirely, so Docker's
restart policy has nothing to act on after daemon restart. But a blanket
`docker compose up -d` on all stacks would resurrect intentionally-stopped services
(e.g. Linguacafe). Solution: save which stacks were active before tearing them down.

**ExecStop (before Docker daemon shuts down):**

1. Detect which compose stacks have running containers
2. Write active stack paths to `/run/homelab-active-stacks`
3. `docker compose down` on ALL stacks (clean removal of containers + containerd tasks)

**ExecStart (after Docker daemon is up):**

1. Read `/run/homelab-active-stacks`
2. `docker compose up -d` only the stacks listed, in dependency order
3. If state file is missing (reboot, power loss): do nothing — Docker's own restart
   policies handle the reboot case (no stale tasks on clean boot), and a missing file
   means we can't know what was intentionally stopped vs running

### Why `/run/`?

`/run/` is tmpfs — survives a daemon restart (same boot session) but cleared on reboot.
This is exactly the right lifetime:

| Scenario | State file exists? | Behavior |
|----------|-------------------|----------|
| Docker daemon restart (update) | Yes | ExecStart restores only active stacks |
| Clean reboot | No | ExecStart is a no-op; Docker restart policies handle it |
| Crash / power loss | No | Same as reboot — restart policies handle it |

On reboot, containers were never removed (the whole machine went down), so there are
no stale containerd tasks. Docker restart policies work correctly. No intervention needed.

### Systemd ordering guarantees

```
                    STOP ORDER                          START ORDER
                    ──────────                          ───────────
homelab-containers.service stops FIRST         docker.service starts FIRST
  └─ save state → docker compose down            └─ daemon is healthy
docker.service stops SECOND                    homelab-containers.service starts SECOND
  └─ daemon shuts down, no containers left       └─ read state → docker compose up -d
```

Achieved via: `After=docker.service` + `PartOf=docker.service`

- `After=docker.service` → starts after Docker, stops before Docker
- `PartOf=docker.service` → automatically stopped when Docker stops

### Stack dependency order

Infrastructure stacks define external networks and must come up first.
Service stacks depend on those networks.

**Start order (for stacks present in state file):**

```
Phase 1 — Infrastructure (sequential, only if in state file):
  1. infrastructure/gateway        (defines traefik_internal, traefik_tunnel)
  2. infrastructure/dns            (defines pihole_network)
  3. infrastructure/cloudflare     (depends on traefik_tunnel)
  4. infrastructure/tailscale
  5. infrastructure/wireguard
  6. infrastructure/wud

Phase 2 — Services (parallel, only those in state file):
  services/* stacks via docker compose up -d simultaneously
```

**Stop order (all stacks, regardless of state):**

```
Phase 1 — Services (parallel):
  All services/ stacks via docker compose down

Phase 2 — Infrastructure (reverse sequential):
  6. infrastructure/wud
  5. infrastructure/wireguard
  4. infrastructure/tailscale
  3. infrastructure/cloudflare
  2. infrastructure/dns
  1. infrastructure/gateway
```

Stop always tears down everything — even stopped stacks — to guarantee no container
metadata or containerd tasks survive.

### Implementation files

| File | Location | Purpose |
|------|----------|---------|
| `homelab-containers.service` | `/etc/systemd/system/` | Systemd unit definition |
| `homelab-up.sh` | `scripts/homelab-up.sh` | Start script (read state, compose up in order) |
| `homelab-down.sh` | `scripts/homelab-down.sh` | Stop script (save state, compose down in reverse) |

### homelab-containers.service (draft)

```ini
[Unit]
Description=Homelab Docker Compose stacks
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/grimur/homelab
ExecStart=/home/grimur/homelab/scripts/homelab-up.sh
ExecStop=/home/grimur/homelab/scripts/homelab-down.sh
TimeoutStartSec=300
TimeoutStopSec=180

[Install]
WantedBy=multi-user.target
```

### homelab-down.sh (draft logic)

```bash
#!/bin/bash
set -euo pipefail
HOMELAB=/home/grimur/homelab
STATE_FILE=/run/homelab-active-stacks

# --- Save state: which stacks have running containers? ---
active=()
for dir in "$HOMELAB"/infrastructure/*/  "$HOMELAB"/services/*/; do
    [ -f "$dir/compose.yaml" ] || continue
    # Check if any container in this stack is running
    if docker compose -f "$dir/compose.yaml" ps -q --status running 2>/dev/null | grep -q .; then
        active+=("$dir")
    fi
done
printf '%s\n' "${active[@]}" > "$STATE_FILE"

# --- Tear down all stacks (running or not) ---
# Phase 1: services (parallel)
for dir in "$HOMELAB"/services/*/; do
    [ -f "$dir/compose.yaml" ] || continue
    docker compose -f "$dir/compose.yaml" down --remove-orphans &
done
wait

# Phase 2: infrastructure (reverse order)
for name in wud wireguard tailscale cloudflare dns gateway; do
    dir="$HOMELAB/infrastructure/$name"
    [ -f "$dir/compose.yaml" ] || continue
    docker compose -f "$dir/compose.yaml" down --remove-orphans
done
```

### homelab-up.sh (draft logic)

```bash
#!/bin/bash
set -euo pipefail
HOMELAB=/home/grimur/homelab
STATE_FILE=/run/homelab-active-stacks

# If no state file, this is a reboot — let Docker restart policies handle it
if [ ! -f "$STATE_FILE" ]; then
    echo "No state file found (reboot?). Skipping — Docker restart policies will handle."
    exit 0
fi

mapfile -t active < "$STATE_FILE"

# Helper: was this stack active?
is_active() { printf '%s\n' "${active[@]}" | grep -qF "$1"; }

# Phase 1: infrastructure (sequential, ordered)
for name in gateway dns cloudflare tailscale wireguard wud; do
    dir="$HOMELAB/infrastructure/$name"
    if is_active "$dir"; then
        docker compose -f "$dir/compose.yaml" up -d
    fi
done

# Phase 2: services (parallel, only active ones)
for dir in "$HOMELAB"/services/*/; do
    [ -f "$dir/compose.yaml" ] || continue
    if is_active "$dir"; then
        docker compose -f "$dir/compose.yaml" up -d &
    fi
done
wait

rm -f "$STATE_FILE"
```

## Scope

- **NAS host only** (`192.168.86.17`). Pi stacks are independent and managed separately.
- **20 stacks** total: 6 infrastructure + 14 services (including beszel-agent, hello-world).
- Does NOT change any compose files, restart policies, images, or volumes.
- Does NOT affect manual `docker compose up/down` workflows — the systemd unit only
  triggers on daemon start/stop.

## Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Docker daemon crash (ExecStop doesn't run) | Medium | No state file → ExecStart is a no-op → restart policies handle it (no stale tasks on crash recovery) |
| `docker compose down` hangs on a stuck container | Low | `TimeoutStopSec=180` forces systemd to proceed |
| Gateway not ready when services start | Low | Sequential start: gateway first, services after |
| Script breaks after adding/removing a service | Low | Auto-discovers stacks via directory listing |
| State file lists a stack that was removed | Low | `[ -f compose.yaml ]` guard skips missing stacks |

## Rollback

```bash
sudo systemctl stop homelab-containers.service
sudo systemctl disable homelab-containers.service
sudo rm /etc/systemd/system/homelab-containers.service
sudo systemctl daemon-reload
```

Containers return to being managed purely by Docker restart policies (pre-existing
behavior). The scripts in `scripts/` are inert without the systemd unit.

## Verification

1. `sudo systemctl enable --now homelab-containers.service` — all stacks come up
2. Manually stop a service: `cd services/linguacafe && docker compose down`
3. `sudo systemctl restart docker` — simulates engine update
4. Verify Linguacafe stays down: `docker compose -f services/linguacafe/compose.yaml ps` — empty
5. Verify active services recovered: `docker ps --format '{{.Names}} {{.Status}}'` — all previously-running containers show "Up"
6. Check Uptime Kuma — all monitored services green after restart

## Impact on other systems

- **BorgBackup**: Unaffected — backs up files, not running containers.
- **WUD**: Restarts alongside other infra stacks — no special handling needed.
- **Auto-update cron**: Container image updates (commit-based) are unaffected. They
  run `docker compose up -d` within individual stacks, not via this unit.
- **ARCHITECTURE.md**: Should be updated to document the systemd unit under Scripts & Tooling.
