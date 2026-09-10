# Milestone 20: Summary — Docker Engine Restart Resilience

## What was changed

Added a systemd service unit and two helper scripts that cleanly remove all Docker
containers before the Docker daemon shuts down (preventing containerd stale-task
exit-128 errors on restart) and restore only the previously-active stacks when the
daemon starts again.

### Files added

| File | Purpose |
|------|---------|
| `scripts/homelab-containers.service` | Systemd unit (copy to `/etc/systemd/system/`) |
| `scripts/homelab-common.sh` | Shared constants (paths, priority order) for up/down scripts |
| `scripts/homelab-up.sh` | ExecStart — restore active stacks from state file |
| `scripts/homelab-down.sh` | ExecStop — save state, tear down all containers |

## Why it was changed

Docker engine updates (via `apt upgrade` / OMV) triggered a containerd bug where stale
task references survived the daemon restart. Affected containers failed with exit code
128 and could not be recovered with `docker restart` — only `docker rm -f` followed by
`docker compose up -d` worked. Observed 2026-09-09: plex, syncthing, ord_dagsins.

## Deviations from plan

1. **Infrastructure ordering:** Plan specified all 6 infra stacks in explicit sequential
   order. Implementation reduces this to 3 priority stacks (`gateway`, `dns`, `cloudflare`)
   with real dependency ordering; remaining infra stacks are auto-discovered from
   `infrastructure/*/` directories. This avoids a hardcoded list that silently skips
   new stacks.

2. **`set -e` removed:** Plan draft used `set -euo pipefail`. Both scripts use
   `set -uo pipefail` (no `-e`) so that individual failures don't abort the entire
   teardown/restore sequence. Failures are tracked and logged instead.

3. **Scripts always exit 0:** Plan didn't specify exit behavior. Both scripts always
   exit 0 regardless of individual failures. This is critical — a non-zero exit from
   `ExecStart` puts the systemd unit in `failed` state, which causes `PartOf=` to skip
   `ExecStop` on the next Docker restart, defeating the stale-task prevention entirely.

4. **Stack count:** Plan states "20 stacks: 6 infrastructure + 14 services." There are
   actually 7 `infrastructure/` directories, but `infrastructure/backup/` has no
   `compose.yaml` so it is auto-skipped by the scripts.

5. **State file path:** Plan used `/run/homelab-active-stacks` (tmpfs). Implementation
   uses `/var/lib/homelab-active-stacks` (persistent). The plan assumed "on reboot,
   containers were never removed" — but with ExecStop enabled, containers ARE removed
   during clean shutdown. A tmpfs state file would be wiped on reboot, leaving no
   record of what to restore. Persistent storage fixes this.

6. **Shared constants file:** Plan listed 3 implementation files. A fourth,
   `scripts/homelab-common.sh`, was added to hold shared constants (`HOMELAB`,
   `STATE_FILE`, `INFRA_PRIORITY`) sourced by both scripts, eliminating duplication.

7. **State detection method:** Plan used per-stack `docker compose ps -q --status running`
   in a loop (~20 sequential calls). During live testing, this proved unreliable under
   systemd stop — some stacks (home-assistant, gateway) were intermittently missed,
   likely due to Docker API contention during daemon shutdown preparation. Replaced with
   a single `docker ps --format '{{.Label "com.docker.compose.project.working_dir"}}'`
   call that reads compose project labels from all running containers atomically.

## New secrets/variables

None.

## ARCHITECTURE.md update needed

Yes — document the systemd unit under **Scripts & Tooling**.

## global.env update needed

No.

## Install procedure

```bash
sudo cp scripts/homelab-containers.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable homelab-containers.service
```
