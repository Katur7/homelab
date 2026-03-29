# Milestone 08.1 Plan: Publish Homelab Repo to GitHub

**Date:** 2026-03-30
**Status:** `COMPLETE`

---

## Overview

Make the homelab repository public on GitHub. Requires a full security audit of all
git-tracked files and git history, removal or scrubbing of any sensitive content, and
establishing safeguards to prevent future accidental commits of secrets.

---

## Scope

1. Audit all tracked files for secrets, personal information, and sensitive config
2. Audit full git history for anything that should not be public
3. Scrub or remove any findings
4. Rotate any exposed credentials
5. Add repo-wide safeguards (gitignore, AI instructions)
6. Push to GitHub as a private or public repository

---

## Risk

**Irreversible:** Once pushed to a public GitHub repo, content is effectively public
permanently — search engines, forks, and caches may index it even if later deleted.
The audit must be thorough before the first push.

**History rewrite:** Scrubbing git history with `git filter-repo` changes all commit
SHAs. Since the repo has no remote at time of execution, no force-push coordination
is needed.

---

## Rollback

History rewrite cannot be undone once complete. Take a full backup of the repo
directory before running `git filter-repo`:

```bash
cp -r /home/grimur/homelab /home/grimur/homelab.bak
```
