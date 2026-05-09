# Milestone 14: 3-2-1 Backup — Summary

## What Changed

### New Borg repository (`borg2`)
- Created `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg2`
- Encryption: `repokey-blake2` (key embedded in repo, passphrase is the only secret)
- Replaces the old `borg/` repo (keyfile-blake2). Old repo left on disk — decommission
  after one week of clean runs: `rm -rf .../backup/borg && rm /root/keyfile.bak.20260429`

### All OMV Borg plugin jobs now point to `borg2`

**`homelab-` daily job (was `homelab--`):**
- Prefix renamed from `homelab--` to `homelab-` (double-dash was a legacy artifact)
- Retention updated: `--keep-daily 14 --keep-weekly 8 --keep-monthly 12`
- Exclusion list significantly expanded — all entries documented at:
  `infrastructure/backup/borg-exclude-homelab.txt`
- Key new exclusions added:
  - `services/immich/database/` — hot Postgres (was previously being hot-copied unsafely)
  - `services/vikunja/db/` — hot Postgres (no dump strategy yet)
  - `services/linguacafe/database/` — hot MySQL (no dump strategy yet)
  - `services/home-assistant/config/*.db / *.db-shm / *.db-wal` — live SQLite
  - Plex live databases and regenerable data (Logs, Media, Codecs, Scanners)
  - PiHole `gravity.db`, `gravity_old.db`, `gravity_backups/`, `listsCache/`, `pihole-FTL.db*`
  - Syncthing `index-v2/` (222MB block index, regenerated on startup)
- Note: plugin does not support `--patterns-from`; exclusions are entered as individual
  entries in the plugin UI. The `.txt` file serves as version-controlled documentation.

**`immich_photos-` weekly job:**
- Pointed to `borg2`
- Retention updated: `--keep-weekly 8 --keep-monthly 12 --keep-yearly 2`
- DB backup handled by Immich's built-in backup scheduler (see below) — no pre-script needed

### Immich database backup — built-in, already working
- Immich's built-in backup dumps `pg_dumpall` output to `photos/backups/` weekly (Saturdays 02:00)
- 4 copies retained (~52MB each compressed)
- This directory is inside the `immich_photos-` source path → captured by borg automatically
- A separate `immich_db-` borg archive was considered and rejected: keeping photos and DB
  in the same archive guarantees a consistent restore point

### Passphrase strengthened
- Old passphrase (4-word diceware) replaced with ≥ 6-word diceware
- Stored in: password manager (primary) + OMV plugin UI (for job scripts)
- No passphrase file on disk yet — deferred to Phase 5 (needed by desktop wrapper script)

---

## Final Archive Layout

| Prefix | Repo | Schedule | Retention |
|--------|------|----------|-----------|
| `homelab-` | `borg2` | Daily 03:30 | 14 daily / 8 weekly / 12 monthly |
| `immich_photos-` | `borg2` | Weekly Mon 03:00 | 8 weekly / 12 monthly / 2 yearly |

---

## What Was Deferred

| Item | Reason |
|------|--------|
| Vikunja logical dump (`pg_dump`) | Out of scope — DB excluded from homelab archive |
| LinguaCafe logical dump (`mysqldump`) | Out of scope — DB excluded from homelab archive |
| Home Assistant recorder dump strategy | HA `.db` files excluded; YAML config is backed up |
| Desktop repo β1 (Phase 5) | Not yet implemented |
| offsite-backup-pi repo (Phase 6) | Blocked on hardware |
| Restore documentation (Phase 7) | Not yet written |
| Failure notifications (Phase 7) | Not yet configured |
| Monthly `borg check` schedule (Phase 7) | Not yet configured |

---

## New Secrets / Variables

| Secret | Where stored |
|--------|-------------|
| Borg passphrase (new, strengthened) | Password manager + OMV plugin UI |

---

## Files Created

| File | Purpose |
|------|---------|
| `infrastructure/backup/borg-exclude-homelab.txt` | Documented exclusion list for `homelab-` archive |
| `specs/14-backup/BACKUP_DESIGN.md` | Full design rationale and decisions |
| `specs/14-backup/plan.md` | Implementation plan |
| `specs/14-backup/summary.md` | This file |

---

## ARCHITECTURE.md Update Required

The Backup Strategy section currently references Milestone 02 and the old `borg/` repo.
Once the old repo is decommissioned, update:
- Repo path: `borg` → `borg2`
- Encryption: keyfile-blake2 → repokey-blake2
- Archive prefixes: add `immich_photos-`, update `homelab-` (single dash)
- Retention: update all values
- Topology: note desktop repo (Phase 5) once complete
