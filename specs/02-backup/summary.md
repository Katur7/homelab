# Milestone 02 Summary: Backup Configuration

**Date:** March 2026
**Status:** `COMPLETED`
**Author:** grimur & NAS Helper (AI)

## 📝 Executive Summary

Configured the OMV BorgBackup plugin to protect `/home/grimur/homelab/`, resolving the known risk from Milestone 01 that the Git repository and git-ignored secrets lived only on the OS drive with no backup.

## 🛠️ What We Did

1. **Defined backup scope:** `/home/grimur/homelab/` only — the repo, its secrets (`global.env`, future `.env` files), and full Git history.
2. **Configured OMV Borg job:** New archive job created in the OMV BorgBackup plugin UI, targeting the existing encrypted Borg repository on the NAS share.
3. **Set exclusions:** `volumes/` only. `.git/` is backed up in full — the repo will stay small (text configs), so packfile bloat is not a concern and full history recovery is more valuable.
4. **Verified backup:** Manual run completed in 1.81 seconds, producing archive `homelab--2026-03-23_09-44-36` (81 files, 52 KB compressed).

## ⚙️ Final Job Configuration

| Setting | Value |
|---------|-------|
| **Source** | `/home/grimur/homelab` |
| **Repository** | `/srv/dev-disk-by-uuid-0ddafbf7-.../backup/borg/` |
| **Archive prefix** | `homelab-` |
| **Compression** | `zstd,3` |
| **Exclusions** | `volumes/` |
| **Schedule** | Daily at 02:00 |
| **Retention** | 7 daily / 4 weekly / 3 monthly |

## ⚓ Key Decisions

- **zstd,3 over lz4:** Better compression ratio for text-heavy content at equivalent speed. Meaningless for current size, but the correct long-term default.
- **Full `.git/` backup:** Dry run revealed no packfiles (young repo). Excluding pack objects would have been overly cautious and would have degraded recovery quality.
- **OMV UI only:** No custom scripts — job is managed entirely through the OMV BorgBackup plugin for consistency with existing backup jobs.

## ⚠️ Known Risks & Technical Debt

- **Local-only backup:** Source (OS drive) and destination (NAS share) are on the same physical machine. A catastrophic hardware failure could lose both. A future milestone should add an offsite destination (e.g., Hetzner Storage Box or Backblaze B2).
- **Shared Borg repo:** The homelab job shares the existing repository with other OMV backup jobs. Monitor repo size as services are added.

## 📋 ARCHITECTURE.md Update Required?

**Yes** — the Backup Strategy section in `ARCHITECTURE.md` has been updated to reflect the final configuration (zstd,3 compression, `volumes/` exclusion only).

## 🏁 Result

The homelab repository is now backed up daily. The next logical step is **Milestone 03: Traefik & Cloudflare Tunnel** — migrating the networking stack from OMV-managed compose files to the GitOps-controlled `infrastructure/` directory.
