# Milestone 08.1 Summary: Publish Homelab Repo to GitHub

**Date:** 2026-03-30
**Status:** `COMPLETE`

---

## What Was Done

### Security Audit

A full audit of all git-tracked files and git history was performed using:
- `git log --all --full-history --diff-filter=A -- '**/.env' '.env'` — no `.env` files
  were ever committed
- `git grep -i "password\|secret\|token\|key"` across all commits — two findings requiring
  action, remainder were `${VAR}` placeholders or acceptable values

### Findings & Remediation

| Finding | Action |
|---------|--------|
| `infrastructure/gateway/config/authelia/users_database.yml` tracked — contained argon2id password hash and real email address | Removed from git index (`git rm --cached`), added to `.gitignore`, git history scrubbed with `git filter-repo` |
| `infrastructure/gateway/config/dynamic/middlewares.yml` — contained plaintext CrowdSec LAPI key in all historical commits | LAPI key rotated (`cscli bouncers delete/add`), key moved to new gitignored `crowdsec.yml`, old key string scrubbed from full history with `git filter-repo --replace-text` |
| `infrastructure/gateway/config/traefik.yml` — contains `grimurk@gmail.com` as ACME email | Accepted — already public via Let's Encrypt CT logs; moving it out of the file is disproportionate effort |
| `infrastructure/gateway/config/authelia/configuration.yml` — contains pbkdf2-sha512 OIDC client secret hashes | Accepted — hashed values, not plaintext secrets |

### Files Added

| File | Purpose |
|------|---------|
| `infrastructure/gateway/config/authelia/users_database.yml.example` | Rebuild reference — documents schema and how to generate argon2 hash |
| `infrastructure/gateway/config/dynamic/crowdsec.yml.example` | Rebuild reference — documents bouncer config; real file is gitignored |

### Gitignore Updates

```
/infrastructure/gateway/config/authelia/users_database.yml
/infrastructure/gateway/config/dynamic/crowdsec.yml
/pi/services/pihole/data/
/pi/services/uptime-kuma/data/
```

### AI Instructions

Added a prominent `## 🔓 Repository Visibility — PUBLIC` section to `AI_INSTRUCTIONS.md`
as the first rule block. Instructs all AI agents to never commit secrets, credentials,
or personal information.

---

## What Was NOT Changed

- `ARCHITECTURE.md`, `README.md`, service compose files — all clean, no changes needed
- Domain names (`pippinn.me`, `*.internal.pippinn.me`) — accepted as public
- Internal LAN IPs — accepted as standard practice for public homelab repos
- CrowdSec default config files (`dev.yaml`, `user.yaml`) — confirmed as shipped
  defaults with placeholder values, not real credentials

---

## Architecture / global.env Changes

None required.

---

## New Secrets / Variables Created

| Secret | Location | Notes |
|--------|----------|-------|
| CrowdSec LAPI key (new) | `infrastructure/gateway/config/dynamic/crowdsec.yml` (gitignored) | Rotated from exposed key — old key is dead |

---

## Post-Publish

- Repo pushed to GitHub as **private** initially
- Can be made public once GitHub remote is configured and verified
