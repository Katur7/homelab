# Milestone 07.4 Plan: OMV — Reduce Email Noise

**Date:** 2026-03-29
**Status:** `PLANNED`

---

## Problem

OMV is sending three categories of unnecessary notification emails.

---

## Identified Email Sources

| Subject pattern | Trigger | Fix |
|-----------------|---------|-----|
| `Cron <root@openmediavault> run-parts .../borgbackup/daily.d/` | BorgBackup daily cron sends stdout/stderr to root, which OMV mails on every successful run | Suppress output on success via scheduled task UI toggle or `MAILTO=""` in crontab |
| `[Fail2Ban] ssh: stopped` / `started` — same for `omv-webgui` | Fail2Ban stops and restarts on every server reboot | Disable Fail2Ban service state notifications in OMV |
| `Your user account was used to log in to the openmediavault control panel` | Fires on every web UI login | Disable login event notifications in OMV |

---

## Fix Steps

All changes are via the **OMV web UI** — no Docker or compose changes involved.

1. **Login notifications:**
   - Go to **System → Notification → General**
   - Uncheck "Login events"

2. **Fail2Ban start/stop notifications:**
   - Go to **System → Notification → Services**
   - Uncheck or remove Fail2Ban (`ssh` and `omv-webgui`) from the monitored services list
   - Note: Fail2Ban cycling on reboot is expected behaviour — suppressing the notification
     is the right fix, not preventing the restart

3. **BorgBackup cron emails:**
   - Go to **Services → Scheduled Tasks**
   - Find the BorgBackup daily job and disable "Send output by email"
   - If no UI toggle is exposed (BorgBackup plugin creates its own cron file in
     `/var/lib/openmediavault/borgbackup/daily.d/`), add `MAILTO=""` to the top of
     `/etc/cron.d/openmediavault-borgbackup` instead

---

## Rollback

Re-enable the suppressed notification rules in OMV via the same UI paths.
