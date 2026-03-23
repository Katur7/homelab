# Milestone 02 Plan: Backup Configuration

**Date:** March 2026
**Status:** `IN PROGRESS`
**Author:** grimur & NAS Helper (AI)

## 🎯 Objective

Configure the existing OMV BorgBackup plugin to protect the `/home/grimur/homelab/` repository. This resolves the known risk from Milestone 01: the Git repo and git-ignored secrets (`.env` files) currently live only on the OS drive with no backup.

## 📦 Backup Scope

| Item | Path | Why |
|------|------|-----|
| Homelab Git repo | `/home/grimur/homelab/` | Contains compose files, specs, architecture docs |
| Git-ignored secrets | `global.env`, `services/**/.env` | Not recoverable from Git — must be in backup |
| Git history | `/home/grimur/homelab/.git/` | Full history on OS drive only |

**Out of scope for this milestone:**
- `/appdata/` service configs (managed by OMV, separate backup job)
- Media/photo shares (too large, separate retention strategy needed)

## 🛠️ OMV BorgBackup Plugin Configuration

Configure a new job in the OMV UI with the following settings:

| Setting | Value |
|---------|-------|
| **Source path** | `/home/grimur/homelab` |
| **Repository** | Existing local repo on NAS share (see ARCHITECTURE.md for path) |
| **Archive name prefix** | `homelab-` |
| **Compression** | `lz4` |
| **Schedule** | Daily at 02:00 |

### Exclusions

```
volumes/
**/.git/objects/pack/
```

- `volumes/` — Docker volume bind-mount data (bulk, not config)
- `.git/objects/pack/` — Large binary packfiles; the working tree is sufficient for recovery

### Retention Policy

| Period | Archives to keep |
|--------|-----------------|
| Daily  | 7               |
| Weekly | 4               |
| Monthly | 3              |

## ⚠️ Pre-Configuration Checklist

Before creating the OMV job:

- [ ] Confirm the Borg repository passphrase is stored in a password manager
- [ ] Verify the existing Borg repo is accessible: `borg list <repo-path>`
- [ ] Note the repo path from the OMV plugin's existing jobs for consistency

## ✅ Verification Steps

1. Trigger a manual run from the OMV UI
2. Check the job log for a successful completion
3. Confirm archive exists: `borg list <repo-path>` — look for `homelab-YYYY-MM-DD`
4. Test a restore: `borg extract <repo>::<archive> home/grimur/homelab/global.env`

## ⚠️ Known Risks

- **Local-only backup:** Both source and destination are on the same physical machine. A full system failure loses both. Offsite backup is a future milestone.
- **Shared repo:** The homelab archives will share the existing Borg repository with other jobs. Ensure the repo has sufficient free space.
