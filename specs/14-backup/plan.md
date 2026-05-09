# Milestone 14: 3-2-1 Backup — Plan

## Goal

Implement a complete 3-2-1 backup strategy for Immich (photos + database) and the
homelab config/secrets folder. Fix the critical gap where Postgres is not being
backed up (and is currently hot-copied unsafely). Add a second independent copy on
the desktop (β1) and lay the groundwork for an offsite Pi copy (Phase 6).

Full design rationale and decisions: [BACKUP_DESIGN.md](BACKUP_DESIGN.md).

---

## Scope

| In scope | Out of scope |
|----------|--------------|
| Immich Postgres logical backup pipeline | Vikunja / LinguaCafe logical dumps (flagged, deferred) |
| homelab- archive exclusions (all DB bind mounts + SQLite) | Home Assistant recorder dump strategy |
| Rename `homelab--` → `homelab-` prefix | offsite-backup-pi setup (Phase 6, blocked on hardware) |
| New repo with repokey-blake2 | |
| Retention policies for all three prefixes | |
| Desktop repo (β1) | |
| Restore documentation | |

---

## Infrastructure Context

| Item | Value |
|------|-------|
| NAS homelab path | `/home/grimur/homelab/` |
| Old Borg repo (keep, do not edit) | `.../backup/borg` — keyfile-blake2 |
| **New Borg repo** | `.../backup/borg2` — repokey-blake2 |
| Immich photos volume | `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos` |
| Immich Postgres container name | `immich_postgres` |
| Passphrase file (Phase 5 only) | `/root/.borg-passphrase` (0600, root-owned) |
| pihole-on-pi | `192.168.86.26` — existing Pi, NOT a backup target |
| offsite-backup-pi | New Pi, to be set up at parents' house — Phase 6 |

All paths under `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/` abbreviated to `.../`.

---

## Archive Prefixes and Retention

| Prefix | Source | Schedule | Retention |
|--------|--------|----------|-----------|
| `immich_photos-` | `.../photos` (incl. Immich's built-in DB dump at `photos/backups/`) | Weekly Mon 03:00 | `--keep-weekly 8 --keep-monthly 12 --keep-yearly 2` |
| `homelab-` | `/home/grimur/homelab/` (with exclusions) | Daily 03:30 | `--keep-daily 14 --keep-weekly 8 --keep-monthly 12` |

Legacy prefix `homelab--*` (double-dash): ages out naturally once the new `homelab-`
job starts writing to `borg2`. No explicit prune needed; the old repo will be
decommissioned entirely.

---

## Known Database Bind Mounts (all inside `/home/grimur/homelab/`)

| Path | Engine | Container | This milestone |
|------|--------|-----------|----------------|
| `services/immich/database/` | Postgres 14 (vectorchord) | `immich_postgres` | pg_dumpall pipeline |
| `services/vikunja/db/` | Postgres 17 | `vikunja-db` | exclude only — dump deferred |
| `services/linguacafe/database/` | MySQL 8 | `linguacafe-database` | exclude only — dump deferred |

Exclusion list maintained at:
`/home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt` (version controlled).

---

## Phase 0 — Pre-flight (COMPLETE)

- [x] Borg version: **1.4.0** (≥ 1.2 required)
- [x] `immich_postgres` container confirmed running and healthy
- [x] OMV plugin config surface mapped:
  - Plugin owns `/etc/cron.d/openmediavault-borgbackup` — never edit
  - Job scripts live in `/var/lib/openmediavault/borgbackup/{cadence}.d/` — never edit
  - Env vars sourced from `/etc/borgbackup/borg-envvar-{uuid}` — plugin-managed
  - Safe locations for hand-managed scripts: `/usr/local/bin/`
- [x] Passphrase strengthened to ≥ 6-word diceware
- [x] `borg list` confirmed working as root with new passphrase

## Phase 1 — New repo (COMPLETE)

Decision: instead of migrating the existing `borg/` repo (keyfile → repokey),
a fresh repo was created. `borg key migrate-to-repokey` does not respect
`BORG_PASSPHRASE` env var in interactive mode on Borg 1.4.0.

- [x] `borg init --encryption=repokey-blake2 .../backup/borg2`
- [x] Verified `Encrypted: Yes (repokey BLAKE2b)`
- [x] Old `borg/` repo left untouched — decommission after one week of clean runs on `borg2`
- [x] `/root/keyfile.bak.20260429` on NAS — delete after decommission

## Phase 2 — Update homelab job in OMV plugin UI

Exclusions file already created at:
`/home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt`

In the OMV Borg plugin, edit the existing daily homelab job:
1. **Repo path**: `.../backup/borg` → `.../backup/borg2`
2. **Archive prefix**: `homelab--` → `homelab-`
3. **Exclusions**: replace all individual `--exclude` flags with:
   `--patterns-from /home/grimur/homelab/infrastructure/backup/borg-exclude-homelab.txt`
4. **Retention**: `--keep-daily 14 --keep-weekly 8 --keep-monthly 12`

After saving, check the generated script under `/var/lib/openmediavault/borgbackup/daily.d/`
to confirm `--patterns-from` appears correctly. Trigger a manual run and verify a
`homelab-{timestamp}` archive appears in `borg list .../backup/borg2`.

## Phase 3 — Add immich_db daily job in OMV plugin UI

Create staging directory first:
```bash
mkdir -p /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/staging/immich_db
chmod 700 /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/staging/immich_db
```

New job config:
- **Repo**: `.../backup/borg2`
- **Archive prefix**: `immich_db-`
- **Source**: `.../backup/staging/immich_db/`
- **Schedule**: daily 03:00 (before homelab job at 03:30)
- **Retention**: `--keep-daily 14 --keep-weekly 8`

Pre-script:
```bash
#!/bin/bash
set -euo pipefail
STAGING=/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/staging/immich_db
mkdir -p "$STAGING"
docker exec -t immich_postgres \
  pg_dumpall --clean --if-exists -U postgres \
  | gzip > "$STAGING/immich-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
```

Post-script:
```bash
#!/bin/bash
rm -f /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/staging/immich_db/*.sql.gz
```

Validation:
- Trigger manually from UI
- `borg list .../backup/borg2 | grep immich_db`
- Confirm staging dir is empty after run
- Test restore on a throwaway container (see Phase 7)

## Phase 4 — Update immich_photos job in OMV plugin UI

Edit the existing weekly immich_photos job:
- **Repo path**: `.../backup/borg` → `.../backup/borg2`
- Prefix, exclusions, and retention unchanged

Trigger a manual run. First run is a full backup (~28GB — will take time).

After one week of clean runs on all three jobs in `borg2`:
```bash
# Decommission old repo
rm -rf /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg
rm /root/keyfile.bak.20260429
```

## Phase 5 — Desktop repo (β1)

Desktop is Bazzite (Fedora-based). NAS acts as Borg client; desktop hosts the repo
via `borg serve`. Desktop never holds the passphrase.

Prerequisites:
- Create `/root/.borg-passphrase` on NAS (0600, root-owned) — needed by wrapper script
- Enable sshd on desktop (disabled by default on Bazzite):
  ```bash
  sudo systemctl enable --now sshd
  sudo firewall-cmd --permanent --add-service=ssh && sudo firewall-cmd --reload
  ```
  Drop `/etc/ssh/sshd_config.d/99-hardening.conf`:
  ```
  PasswordAuthentication no
  PermitRootLogin no
  ```
  Consider binding sshd to Tailscale interface only (`ListenAddress 100.x.x.x`)
  if Tailscale is active on desktop.

Steps:
- [ ] Create `borg` system user on desktop (locked password, restricted shell)
- [ ] Create repo directory on desktop, e.g. `/home/borg/repos/nas/`
- [ ] Add forced-command entry in `~borg/.ssh/authorized_keys` for NAS SSH key:
  ```
  command="borg serve --restrict-to-repository /home/borg/repos/nas/",no-pty,no-agent-forwarding,no-X11-forwarding,no-port-forwarding ssh-ed25519 AAAA...
  ```
- [ ] Init repo from NAS (passphrase never leaves NAS):
  ```bash
  BORG_PASSCOMMAND='cat /root/.borg-passphrase' \
  borg init --encryption=repokey-blake2 \
    ssh://borg@desktop/home/borg/repos/nas/
  ```
- [ ] Create `/usr/local/bin/backup-to-desktop.sh` on NAS:
  - Runs `borg create` for all three prefixes against desktop repo
  - Reads passphrase via `BORG_PASSCOMMAND='cat /root/.borg-passphrase'`
  - `immich_db-` uses same `pg_dumpall` + staging approach as Phase 3
  - `chmod 700`
- [ ] Create a second SSH keypair on desktop authorised only to invoke that wrapper:
  (forced command in NAS root's `authorized_keys`):
  ```
  command="/usr/local/bin/backup-to-desktop.sh",no-pty,no-agent-forwarding ssh-ed25519 AAAA...
  ```
  A compromised desktop can only trigger that one script — cannot browse source files
  or run arbitrary NAS commands.
- [ ] Install desktop systemd service + timer:
  - `OnCalendar=daily`, `Persistent=true`, `RandomizedDelaySec=10min`
  - Service: `systemd-inhibit --what=sleep --who=borg --why="backup" ssh root@nas` (restricted key)
- [ ] Test: sleep desktop past scheduled time, wake, confirm new archive in desktop repo

## Phase 6 — offsite-backup-pi (deferred)

Blocked on: `offsite-backup-pi` hardware acquisition and setup.

Design decisions already made:
- Pi only runs `borg serve --restrict-to-repository` — never holds passphrase
- NAS pushes to Pi over Tailscale (preferred) or WireGuard (TBD)
- Cadence: weekly (to protect parents' uplink)
- Throttle with `--upload-ratelimit`

Open items:
- Tailscale vs WireGuard for the Pi link
- Exact throttle value (depends on parents' uplink speed)

## Phase 7 — Verification and monitoring

- [ ] Document restore procedure in `specs/14-backup/restore.md`:
  - Immich: extensions must be initialised before `psql < dump.sql.gz` — follow official Immich docs
  - homelab: restore from archive, re-run `docker compose up -d` per service
- [ ] Test restore from NAS repo (homelab + immich_db at minimum)
- [ ] Test restore from desktop repo once Phase 5 is complete
- [ ] Failure notification: choose one (gotify, ntfy, healthchecks.io, systemd `OnFailure=`) — TBD
- [ ] Schedule monthly `borg check` on each repo (first Sunday of month, low priority)

---

## Rollback

| Phase | Rollback |
|-------|---------|
| 1 (new repo) | `borg2` can be deleted; repoint plugin jobs back to `borg` |
| 2 (exclusions) | Remove `--patterns-from`; re-add individual `--exclude` flags |
| 3 (DB pipeline) | Delete `immich_db-` job from plugin; remove staging dir |
| 4 (photos) | Repoint `immich_photos-` job back to `borg` |
| 5 (desktop) | Delete desktop systemd units; remove `/usr/local/bin/backup-to-desktop.sh` |

---

## Files Changed / Created

| File | Action |
|------|--------|
| `specs/14-backup/plan.md` | This file |
| `specs/14-backup/BACKUP_DESIGN.md` | Pre-existing design doc (unchanged) |
| `infrastructure/backup/borg-exclude-homelab.txt` | New — exclusion patterns for homelab- archive |
| `/usr/local/bin/backup-to-desktop.sh` | New on NAS (Phase 5) — host-managed, not in repo |
| `specs/14-backup/restore.md` | New — restore procedure (Phase 7) |

After successful completion: update `ARCHITECTURE.md` Backup Strategy section to
reflect the new 3-repo topology, new repo path (`borg2`), and replace the Milestone 02 reference.

---

## New Secrets / Variables Required

| Secret | Where stored | Notes |
|--------|-------------|-------|
| Borg passphrase | Password manager + `/root/.borg-passphrase` (0600, Phase 5+) | Never committed |
| NAS SSH key for desktop trigger | Desktop `~/.ssh/` (private) + NAS `authorized_keys` (public) | Forced-command restricted |
| Desktop SSH key for borg user | NAS side (private) + desktop `borg` user `authorized_keys` (public) | Forced-command restricted |
