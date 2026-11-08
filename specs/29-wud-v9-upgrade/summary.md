# Milestone 29 Summary: What's Up Docker (WUD) v9 Upgrade & Authentication Hardening

## 🎯 What Was Done

1. **WUD v9 Upgrade:**
   - Upgraded What's Up Docker from `8.4.0` to `9.7.0` in [`infrastructure/wud/compose.yaml`](file:///Users/grimur/personal-code/homelab/infrastructure/wud/compose.yaml).
   - Added persistent SQLite store bind mount (`./store:/store`) with `1000:1000` ownership and `750` permissions to persist `wud.sqlite`, user sessions, and API tokens.
   - Added `/infrastructure/wud/store/` to [`.gitignore`](file:///Users/grimur/personal-code/homelab/.gitignore) (backed up by Borg daily).
   - Declared explicit Traefik loadbalancer port `3000`.

2. **Single Sign-On (SSO) via Authelia OIDC:**
   - Registered `wud` OIDC client in [`infrastructure/gateway/config/authelia/configuration.yml`](file:///Users/grimur/personal-code/homelab/infrastructure/gateway/config/authelia/configuration.yml) with:
     - `token_endpoint_auth_method: 'client_secret_post'`
     - `userinfo_signed_response_alg: 'none'`
     - `require_pkce: false`
     - Scopes: `openid`, `profile`, `email`, `groups`
   - Configured OIDC parameters in [`infrastructure/wud/vars.env`](file:///Users/grimur/personal-code/homelab/infrastructure/wud/vars.env) with role mapping to the `admins` group.
   - Configured `WUD_AUTH_SESSION_SECRET` for stable session cookie persistence across container restarts.

3. **REST API & Skill Automation Authentication:**
   - Provisioned personal API token (`WUD_API_TOKEN`) in `infrastructure/wud/.env`.
   - Updated [`.claude/skills/check-updates/SKILL.md`](file:///Users/grimur/personal-code/homelab/.claude/skills/check-updates/SKILL.md) and [`scripts/check-updates.py`](file:///Users/grimur/personal-code/homelab/scripts/check-updates.py) to authenticate queries to `/api/containers` using the Bearer token.
   - Successfully verified `python3 scripts/check-updates.py` discovering available updates without authentication errors.

---

## 💡 Why It Was Done

- **WUD v9 Breaking Changes:** Version 9 removed anonymous access entirely and introduced a mandatory authentication fail-fast startup gate, requiring either provisioned admin credentials or an OIDC provider.
- **Persistence Architecture:** Migrated internal engine from in-memory/LokiJS to SQLite via Drizzle ORM, necessitating host-level persistent storage for users, sessions, and container metadata.
- **SSO Uniformity:** Enforces the homelab's central identity provider (Authelia) for dashboard login with Passkey/2FA protection, eliminating separate credentials for human access while isolating machine access via scoped API tokens.

---

## 🔑 New Secrets & Variables Created

| Variable | Location | Purpose |
|----------|----------|---------|
| `WUD_AUTH_OIDC_AUTHELIA_CLIENTSECRET` | `infrastructure/wud/.env` (gitignored) | Plaintext OIDC secret matching Authelia client PBKDF2 hash |
| `WUD_AUTH_SESSION_SECRET` | `infrastructure/wud/.env` (gitignored) | Cryptographic 32-byte hex secret for UI session cookie signing |
| `WUD_AUTH_ADMIN_USER` | `infrastructure/wud/.env` (gitignored) | Break-glass local admin fallback username |
| `WUD_AUTH_ADMIN_PASSWORD` | `infrastructure/wud/.env` (gitignored) | Break-glass local admin fallback password |
| `WUD_API_TOKEN` | `infrastructure/wud/.env` (gitignored) | Personal API token used by `check-updates.py` and skills |

---

## 📋 Architecture & Environment Impacts

- **`global.env`:** No updates required.
- **`ARCHITECTURE.md`:** No architectural changes required; storage follows standard `infrastructure/<service>/` patterns covered by BorgBackup.
