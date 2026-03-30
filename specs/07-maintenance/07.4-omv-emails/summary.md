# Milestone 07.4 Summary: Stop OMV Excessive Notification Emails

**Date:** 2026-03-30
**Status:** `COMPLETE`

---

## What Was Changed

### 1. Fail2Ban — suppress start/stop emails (keep ban emails)

**Root cause:** `/etc/fail2ban/jail.conf` sets `action = %(action_mwl)s` globally.
This action sends email on jail start, stop, ban, and unban. On every reboot, the
`ssh` jail emits 2 emails (start + stop).

CrowdSec does not monitor SSH, so ban emails from Fail2Ban are needed and were kept.

**Files created (outside repo — system-managed):**

`/etc/fail2ban/action.d/sendmail-whois-lines-banonly.conf`
```ini
[INCLUDES]
before = sendmail-whois-lines.conf

[Definition]
actionstart =
actionstop =
```

`/etc/fail2ban/jail.local`
```ini
[DEFAULT]
action = %(banaction)s[name=%(__name__)s, ...]
         sendmail-whois-lines-banonly[name=%(__name__)s, dest="%(destemail)s", chain="%(chain)s"]
```

Reloaded with `fail2ban-client reload` — ssh jail confirmed active.

### 2. OMV web UI — disable login event emails

OMV 7 no longer has a "Services" event category (removed vs OMV 6).
Disabled via System → Notification → Events → **Authentication** (unchecked).

### 3. BorgBackup cron — disable email output

Old `/appdata` backup job was sending cron completion emails.
Disabled "Send output by email" in System → Scheduled Tasks.

---

## No Secrets / Variables Created

No changes to `.env`, `global.env`, or compose files.

## No Architecture / global.env Changes Required

---

## Note

The Fail2Ban config files (`/etc/fail2ban/`) are outside the GitOps repo and will not
survive a full OS reinstall without manual recreation. If OMV is ever reinstalled,
recreate `jail.local` and `sendmail-whois-lines-banonly.conf` from this summary.
