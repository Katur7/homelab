# Immich + Homelab Backup Design

Handoff document for an agent working in the `homelab` repo with NAS access.
Captures every decision reached during the design conversation so you can
implement without re-litigating the design.

User: grimur. NAS runs OpenMediaVault. Goal: 3-2-1 backup of Immich (photos
+ database) and the homelab config/secrets folder.

## Architecture summary

```
                  ┌─────────────────────────────────────────┐
                  │ NAS (OpenMediaVault, source of truth)   │
                  │  - Immich photos at                     │
                  │    /srv/dev-disk-by-uuid-0ddafbf7-      │
                  │      f06d-424d-8e9c-95d97fbd4484/photos │
                  │  - Postgres (vectorchord) in compose    │
                  │    bind mount ./database                │
                  │  - homelab/ folder (config + secrets)   │
                  └────────────┬────────────────────────────┘
                               │
        ┌──────────────────────┼──────────────────────────┐
        ▼                      ▼                          ▼
 NAS-local repo        Desktop repo (β1)        Pi repo (future)
 daily, fast restore   on-wake, opportunistic   weekly, offsite
 already exists        irregularly-on machine   Pi at parents' house
```

All three are independent Borg repositories, all `repokey-blake2`, all share
one passphrase. The Pi never holds the passphrase itself — it only runs
`borg serve --restrict-to-repository`.

Each repo holds three archive prefixes:

| Prefix             | Source                                         | Cadence       |
| ------------------ | ---------------------------------------------- | ------------- |
| `immich_photos-`   | photos folder (excl. thumbs, encoded-video)    | weekly Mon 03:00 |
| `immich_db-`       | `pg_dumpall` output (NEW)                      | daily         |
| `homelab-`         | homelab/ folder (drop legacy double-dash name) | daily 03:30   |

## Current state (as of 2026-04-29)

### Existing Borg repo

- Path: `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg`
- Repo ID: `ad4589c5486d8d4e3e25fdb488777ee3682fa25b5ed6fd0ee64d084748ab331e`
- Encryption: **keyfile-blake2** (or similar keyfile mode)
- Key file: `/root/.config/borg/keys/srv_dev_disk_by_uuid_0ddafbf7_f06d_424d_8e9c_95d97fbd4484_backup_borg`
- Sizes: 336 GB original → 33 GB deduplicated
- Existing archive prefixes:
  - `immich_photos-*` weekly Mondays 03:00
  - `docker_config-*` legacy, last archive 2026-03-30 (defunct)
  - `homelab--*` daily 03:30, started 2026-03-23 (the rename of docker_config; keeps the double-dash)

### Immich setup

- Compose file: https://github.com/Katur7/homelab/blob/main/services/immich/compose.yaml
- Photos volume: `/srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/photos:/data`
- Postgres image: `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0`
- Postgres bind mount: `./database:/var/lib/postgresql/data` (relative to the
  immich compose file, almost certainly inside the `homelab/` folder)
- Postgres env: `POSTGRES_USER=postgres`, `POSTGRES_DB=immich`,
  `POSTGRES_INITDB_ARGS=--data-checksums`
- Immich version pin: `${IMMICH_VERSION:-v2.6.1}`

### Storage layout

- NAS: 4 main drives, SnapRAID (3 storage + 1 parity). No native filesystem
  snapshots — Borg is the snapshot mechanism.
- Desktop: irregularly on. Mostly slept, occasionally booted. Used for editing.
- Pi: at parents' house. Not yet online. Will be the offsite copy.

### Critical gap

Postgres is **not currently being backed up**. If `homelab/` Borg archive
includes the `./database` bind-mount path, that's a hot filesystem-level
copy of running Postgres state with vectorchord indexes — which Immich docs
explicitly say is **unsafe** (vector indexes can fail to restore). This must
change to `pg_dumpall`-based logical backup, and the bind-mount path must be
excluded from the homelab archive.

## Decisions

### Encryption and keys

1. **Migrate the existing repo from keyfile to repokey.** The user does not
   want to manage a separate keyfile (their password manager doesn't accept
   file uploads). Repokey embeds the encryption key inside the repo, so
   backing up the repo backs up the key. Passphrase is the only secret.

   ```
   borg key change-location \
     /srv/dev-disk-by-uuid-0ddafbf7-f06d-424d-8e9c-95d97fbd4484/backup/borg \
     repokey
   ```

   This is metadata-only, does not re-encrypt data, is reversible, and
   keeps the passphrase the same. Requires Borg ≥ 1.2.

2. **All three repos use `repokey-blake2`, same passphrase.**
   - Threat-model rationale (already discussed and decided):
     - Pi physical theft alone: thief has only the encrypted repo, no
       passphrase (passphrase never lives on Pi). Encryption holds. Same
       outcome regardless of whether passphrase is shared.
     - The narrow scenario where separate passphrases help (password-manager
       leak + physical theft of Pi) is judged not worth the operational
       overhead of three secrets.
   - The real security improvement is **the Pi never holds the passphrase**,
     not separate passphrases per repo.

3. **Passphrase storage:**
   - Password manager: primary copy.
   - On NAS: in a 0600-permission file readable only by the borg-running user
     (root in this case, given the cron context). Used by `BORG_PASSCOMMAND`
     or `BORG_PASSPHRASE`. **All borg client invocations run on the NAS**,
     so this is the only machine that ever holds the passphrase.
   - On desktop: **not needed**. In β1 the borg client runs on the NAS; the
     desktop only hosts the repo via `borg serve`. Desktop's trigger script
     only needs an SSH key into the NAS to kick off the backup script.
   - On Pi: never. Pi only runs `borg serve --restrict-to-repository`.

4. **Passphrase strength check:** before migration, verify the existing
   passphrase is strong (≥ 6-word diceware or ≥ 30 random chars). If not,
   `borg key change-passphrase` first.

### Archive prefixes

5. **Three prefixes per repo:**
   - `immich_photos-` — Immich photo originals (matches existing name)
   - `immich_db-` — `pg_dumpall` output (new)
   - `homelab-` — homelab folder (rename from existing `homelab--`; drop the
     double-dash artifact)

6. **DB and photos share the same repo, different prefixes.** Per-prefix
   retention via `borg prune --glob-archives` gives separate lifecycles
   without separate repos. Restoration is a logical pair (photos + DB), so
   co-location is correct.

### Cadence

7. **Schedule:**
   - `immich_photos-`: weekly, Monday 03:00 (unchanged)
   - `immich_db-`: daily (small, high churn — face tags, uploads, edits)
   - `homelab-`: daily, 03:30 (unchanged)

8. **Atomicity for DB:** `pg_dumpall` runs and completes before the
   `immich_db-` borg archive is created. Sequence in one wrapper:
   1. `docker exec immich_database pg_dumpall ... | gzip > /staging/dump.sql.gz`
   2. `borg create ::immich_db-{now} /staging/`
   3. `rm /staging/dump.sql.gz`
   The dump and its archive are bound together; no race with concurrent
   borg runs as long as the wrapper is the only thing writing this prefix.

### Retention (per archive prefix)

```
immich_photos-*  --keep-weekly 8 --keep-monthly 12 --keep-yearly -1
immich_db-*      --keep-daily 14 --keep-weekly 8
homelab-*        --keep-daily 14 --keep-weekly 8 --keep-monthly 12
```

Photos kept forever (yearly = -1 = unlimited). DB only needs recent history
for restore. Homelab tracks config drift, gets a year of monthlies.

### Topology

9. **NAS local repo:** existing path, daily writes, primary restore source.

10. **Desktop repo (β1, desktop-pull on wake):**
    - Desktop runs a systemd timer with `Persistent=true`,
      `OnCalendar=daily`, `RandomizedDelaySec=10min`. After resume from
      sleep, systemd notices missed runs and fires.
    - The triggered service on desktop runs a thin script that:
      1. Uses `systemd-inhibit --what=sleep` to prevent suspend during run.
      2. SSHes into the NAS and invokes a NAS-side script
         (e.g. `ssh root@nas /usr/local/bin/backup-to-desktop.sh`).
    - The NAS-side script then runs the actual borg command:
      `borg create ssh://borg@desktop/path/to/repo::immich_photos-{now} /srv/.../photos`
      (and similarly for `homelab-` and `immich_db-`). `BORG_PASSPHRASE` is
      read on the NAS via `BORG_PASSCOMMAND='cat /root/.borg-passphrase'`.
    - Desktop hosts the repo via `borg serve --restrict-to-repository`
      under a dedicated `borg` SSH user with a forced-command in
      `authorized_keys`. Desktop **never holds the passphrase**.
    - Borg client runs on the NAS (where source data is); dedup happens
      NAS-side; only changed chunks ship over LAN.
    - Independent repo. NAS repo corruption does not propagate.

11. **Pi repo (future, NAS push):**
    - Pi runs `borg serve --restrict-to-repository /path/to/repo` over SSH.
      Pi never holds the passphrase.
    - NAS pushes weekly over Tailscale or WireGuard (decision TBD — see
      open items).
    - Throttle bandwidth (`--upload-ratelimit`) so it doesn't saturate the
      parents' uplink.

## Scheduling: OMV plugin vs. systemd

The OMV Borg plugin supports **per-archive pre-script and post-script**
hooks, which means the DB dump pipeline fits the plugin model after all.
Keep nearly everything in the UI:

**Keep in OMV plugin (UI-managed):**
- `immich_photos-` weekly job → NAS-local repo (existing, no change)
- `homelab-` daily job → NAS-local repo (rename from `homelab--`, add
  `./database` exclusion)
- `immich_db-` daily job → NAS-local repo (NEW). Configured as:
  - Source path: `/srv/.../backup/staging/immich_db/`
  - **Pre-script**: `docker exec <immich_postgres_container> pg_dumpall
    --clean --if-exists -U postgres | gzip > /srv/.../backup/staging/immich_db/immich-$(date -u +%Y%m%dT%H%M%SZ).sql.gz`
  - **Post-script**: `rm -f /srv/.../backup/staging/immich_db/*.sql.gz`
  - Schedule: daily
  - Prune: `--keep-daily 14 --keep-weekly 8`
- Pi push (Phase 6) **if** the plugin supports SSH-remote repositories
  with forced-command setups. Worth trying first.
- Prune policies for all of the above.

**Only as systemd / hand-managed scripts:**
- NAS-side wrapper script for desktop push (β1) — this is invoked
  *on demand* when the desktop SSHes in to trigger it, not on a schedule.
  No timer, just a script in `/usr/local/bin/`.
- Pi push **if** the plugin can't handle SSH-remote with our forced-command
  hardening — fall back to systemd timer. Decide during Phase 6.

**Investigation needed before adding anything by hand:**
- Where does the OMV plugin write its config? Likely `/etc/cron.d/`, OMV's
  conf db (`/etc/openmediavault/config.xml`), and possibly systemd units
  it manages. Editing plugin-owned files by hand can be silently
  overwritten on the next plugin save. Hand-managed scripts (the desktop
  push wrapper) should live in clearly separate locations
  (`/usr/local/bin/`, custom systemd unit names) so the plugin won't
  touch them.

## Implementation plan

### Phase 0 — Pre-flight on NAS

- [ ] Confirm Borg version on NAS: `borg --version` (must be ≥ 1.2 for
      `borg key change-location`).
- [ ] Map the OMV Borg plugin's config surface: which files does it own
      (cron entries, systemd units, OMV conf.xml fragments)? Document so
      hand-managed systemd units land in clearly separate locations and
      don't get clobbered by the next plugin save.
- [ ] Verify passphrase strength; if weak, `borg key change-passphrase`
      before migration.
- [ ] Verify `borg list` works as the user that runs the cron job (root,
      based on the keyfile location). The interactive `borg info` from the
      `grimur` user fails because it can't read the root-owned keyfile —
      do all repo work as root or under sudo.

### Phase 1 — Migrate existing repo to repokey

- [ ] `cp /root/.config/borg/keys/srv_dev_disk_..._backup_borg /root/keyfile.bak`
- [ ] Pause the existing backup service / disable cron.
- [ ] `borg key change-location /srv/.../backup/borg repokey`
- [ ] `borg info /srv/.../backup/borg` — confirm `Encrypted: Yes (repokey)`.
- [ ] `borg list /srv/.../backup/borg | tail -1` — confirm archives still
      readable.
- [ ] Resume cron, run a manual archive, confirm success.
- [ ] Delete the original keyfile and the `.bak` after one successful run
      (do not delete prematurely).

### Phase 2 — Investigate homelab exclusions

This is the part the agent must figure out — it requires looking at the
actual NAS contents.

- [ ] Map the homelab folder: `du -h --max-depth=2 /path/to/homelab/ | sort -h`
- [ ] **Mandatory exclusion: the Immich Postgres bind mount**. The compose
      file uses `./database:/var/lib/postgresql/data`, so the path is
      almost certainly `homelab/services/immich/database/`. Confirm and
      add to the borg exclude list. This is the hot-DB-files-in-archive
      bug we are explicitly fixing.
- [ ] Identify other database bind mounts (any service running Postgres /
      MySQL / MariaDB / Redis with persistence has the same problem).
      Each one needs its own logical-dump strategy (out of scope for this
      iteration, but flag them).
- [ ] Identify regenerable / large data:
      - `*/cache/`, `*/logs/`, `*/tmp/`
      - Plex / Jellyfin metadata (`MediaCover`, transcode caches)
      - Home Assistant `*.db-shm` / `*.db-wal` (live SQLite WAL — should
        either dump separately or stop HA before backup)
      - `node_modules/`, `__pycache__/`, `.venv/`, build artifacts
- [ ] Write the exclude list as a `--patterns-from` file in the homelab
      repo, version controlled.

### Phase 3 — Add the DB backup pipeline

Implemented as a new archive in the OMV Borg plugin using its pre/post
script hooks — no separate systemd timer needed.

- [ ] Confirm the Postgres container name on the NAS:
      `docker compose -f /path/to/immich/compose.yaml ps`. The compose
      service is called `database`; container name will be something like
      `immich-database-1` or `immich_database_1`. Pin this in the
      pre-script.
- [ ] Create the staging directory: `/srv/.../backup/staging/immich_db/`
      (0700, owned by whichever user the plugin runs jobs as).
- [ ] In the OMV Borg plugin UI, create a new archive:
      - Name prefix: `immich_db-`
      - Source: `/srv/.../backup/staging/immich_db/`
      - Schedule: daily
      - Pre-script:
        ```
        #!/bin/bash
        set -euo pipefail
        STAGING=/srv/.../backup/staging/immich_db
        mkdir -p "$STAGING"
        docker exec -t <container_name> \
          pg_dumpall --clean --if-exists -U postgres \
          | gzip > "$STAGING/immich-$(date -u +%Y%m%dT%H%M%SZ).sql.gz"
        ```
      - Post-script:
        ```
        #!/bin/bash
        rm -f /srv/.../backup/staging/immich_db/*.sql.gz
        ```
      - Prune: `--keep-daily 14 --keep-weekly 8`
- [ ] Trigger the job manually from the UI, confirm `immich_db-{now}`
      archive appears in `borg list` and the staging dir is empty after.
- [ ] Test restore end-to-end on a throwaway Postgres container before
      considering Phase 3 done. Document the restore procedure.

### Phase 4 — Update archive naming and retention

All three prefixes are now managed by the OMV Borg plugin (after Phase 3),
so all prune config lives in the plugin UI.

- [ ] Through the plugin UI, update the homelab job archive prefix from
      `homelab--` to `homelab-` (single dash). Old `homelab--*` archives
      age out naturally via prune.
- [ ] In the plugin, configure prune per archive prefix per the retention
      table:
      - `immich_photos-*` → keep-weekly 8, keep-monthly 12, keep-yearly -1
      - `immich_db-*`     → keep-daily 14, keep-weekly 8
      - `homelab-*`       → keep-daily 14, keep-weekly 8, keep-monthly 12
      If the plugin's retention config is per-job (rather than per-prefix),
      that's fine — each job already maps 1:1 to a prefix.

### Phase 5 — Desktop repo (β1)

- [ ] **Prerequisite: enable sshd on desktop.** The β1 model requires the
      NAS to SSH into the desktop to run `borg serve`. Bazzite ships sshd
      installed but disabled. Enable and harden:
      ```
      sudo systemctl enable --now sshd
      sudo firewall-cmd --permanent --add-service=ssh
      sudo firewall-cmd --reload
      ```
      Drop in `/etc/ssh/sshd_config.d/99-hardening.conf`:
      ```
      PasswordAuthentication no
      PermitRootLogin no
      ```
      If Tailscale is in use on the desktop, consider binding sshd to the
      Tailscale interface only (`ListenAddress 100.x.x.x` in
      sshd_config.d) so it isn't exposed on the LAN.
- [ ] On desktop: create a `borg` system user with locked password
      (`usermod -L borg`). No login shell needed beyond what `borg serve`
      requires.
- [ ] Init the repo. Two options:
      - Easiest: SSH into desktop as the `borg` user from the NAS and run
        `borg init --encryption=repokey-blake2 ssh://borg@desktop/path/to/repo`
        from the NAS side, supplying the shared passphrase from the NAS's
        passphrase file. This way the passphrase is only ever typed/read
        on the NAS.
- [ ] On desktop's `borg` user: `~/.ssh/authorized_keys` entry for the NAS
      with a forced command like
      `command="borg serve --restrict-to-repository /path/to/repo",no-pty,no-agent-forwarding,no-X11-forwarding,no-port-forwarding ssh-ed25519 AAAA...`
      so even the NAS key can only do `borg serve` against this one repo.
- [ ] On NAS: a wrapper script `/usr/local/bin/backup-to-desktop.sh` that
      runs the three `borg create` commands against the desktop repo,
      reading the passphrase from `/root/.borg-passphrase` (0600).
- [ ] On desktop: a separate SSH key authorized only to invoke that NAS-side
      wrapper script (forced command in NAS root's `authorized_keys`,
      restricting to `/usr/local/bin/backup-to-desktop.sh`). This means a
      compromised desktop can only ask the NAS to run that one backup
      script — it cannot read source files or run arbitrary commands.
- [ ] Desktop systemd timer (`Persistent=true OnCalendar=daily
      RandomizedDelaySec=10min`) and service that:
      1. `systemd-inhibit --what=sleep --who=borg --why="backup"` wraps...
      2. `ssh root@nas` (using the restricted key) which triggers the
         NAS-side wrapper.
- [ ] Test: sleep desktop, wait past the OnCalendar time, wake, confirm
      timer fires and a new archive lands on the desktop repo.

### Phase 6 — Pi repo (when Pi is online)

Open until the Pi is set up. Decide: Tailscale or WireGuard? Throttle
settings? Cadence weekly is the current intent, may revise based on
parents' uplink.

### Phase 7 — Verification and monitoring

- [ ] Document the **restore procedure** in the homelab repo. Include
      pg_dumpall restore steps (it's not just `psql < dump.sql` — Immich
      requires specific extension setup; check Immich docs for the
      official restore sequence).
- [ ] Test restore from each repo at least once.
- [ ] Failure notification — currently undecided. Options: gotify, email,
      ntfy, healthchecks.io. Pick one. systemd `OnFailure=` units make
      this easy.
- [ ] `borg check` schedule: monthly on each repo (it's slow; weekend job).

## Open items deferred to implementation

- Exact homelab exclusion list (depends on Phase 2 investigation)
- Tailscale vs WireGuard for the Pi link
- Pi cadence / throttle settings
- Failure notification mechanism
- Whether other services in homelab also need pg_dump / mysqldump pipelines
  (Phase 2 will surface them)

## References

- Immich official backup docs:
  https://immich.app/docs/administration/backup-and-restore
- Borg key change-location:
  https://borgbackup.readthedocs.io/en/stable/usage/key.html
- Compose file for Immich (current pin: v2.6.1):
  https://github.com/Katur7/homelab/blob/main/services/immich/compose.yaml
