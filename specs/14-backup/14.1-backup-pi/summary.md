# Milestone 14.1: Backup Pi — Summary

## What was done

Configured a Raspberry Pi 4 at an offsite location (parents' house) as a borg
backup target for the NAS, accessible only via Tailscale.

### Phase 1 — OS Hardening & log2ram
- Verified `unattended-upgrades` enabled with auto-reboot at 05:00
- Installed `log2ram` to reduce SD card writes

### Phase 2 — Borg User Setup
- Created dedicated `borg` user with locked password
- Generated ed25519 SSH keypair on NAS (`/root/.ssh/id_ed25519_backup_pi`)
- Configured `authorized_keys` with `restrict` + forced `borg serve` command
- Repo restricted to `/mnt/backup/borg-repo`

### Phase 3 — Repo Init
- Initialized borg repo with `repokey-blake2` encryption
- Passphrase stored in `/root/.borg-passphrase` on NAS (not in git)

### Phase 4 — Test Backups
- Manual `homelab` archive: ~553 MB original, deduplicates well
- Manual `immich_photos` archive: ~30.5 GB (photos + Immich DB dumps)
- Total repo size on disk: ~31 GB

### Phase 5 — Automated Script & Schedule
- Created `infrastructure/backup/backup-to-pi.sh` (git-tracked)
- Cron: weekly Sunday 04:00 via `/etc/cron.d/backup-to-pi`
- Retention: homelab 14d/8w/12m, photos 8w/12m/2y
- Upload rate limited to ~10 MB/s (`--upload-ratelimit 10000`)

### Phase 6 — SMART Monitoring
- Installed `smartmontools` on pi-backup
- Drive: Seagate Barracuda ST4000LM024 4TB — PASSED, 0 reallocated sectors
- `smartd` enabled for ongoing monitoring

## Files changed/created

| File | Action |
|------|--------|
| `infrastructure/backup/backup-to-pi.sh` | New — push script |
| `specs/14-backup/14.1-backup-pi/plan.md` | New — plan |
| `specs/14-backup/14.1-backup-pi/summary.md` | New — this file |

## Host-managed files (not in git)

| File | Host | Purpose |
|------|------|---------|
| `/root/.ssh/id_ed25519_backup_pi` | NAS | SSH key for borg |
| `/root/.borg-passphrase` | NAS | Borg repo passphrase |
| `/etc/cron.d/backup-to-pi` | NAS | Weekly cron schedule |
| `/home/borg/.ssh/authorized_keys` | pi-backup | Forced borg serve |
| `/mnt/backup/borg-repo` | pi-backup | Borg repository |

## Open items

- Failure notifications — deferred to spec 14 Phase 7
- `borg check` schedule — deferred to spec 14 Phase 7
- Beszel agent on pi-backup for general system monitoring — requires Tailscale on pihole-pi or alternative hub placement
- Upload rate tuning — 10 MB/s conservative, actual throughput was much faster
