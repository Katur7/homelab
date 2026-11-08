# EGM Goldfish Review Report: Milestone 29 (WUD v9 Upgrade)

* **Target Document:** [`specs/29-wud-v9-upgrade/plan.md`](file:///Users/grimur/personal-code/homelab/specs/29-wud-v9-upgrade/plan.md)
* **Date:** 2026-10-31
* **Mode:** UNINTERRUPTED PIPELINE
* **Reviewers:** `egm-zoom-out`, `egm-comprehension`, `egm-design`, `egm-codebase-details`, `egm-implementation-readiness`

---

## 1. Executive Summary & Paraphrase

### System Understanding
The document proposes upgrading What's Up Docker (WUD) from version `8.4.0` to `9.7.0` on the Debian NAS host. WUD v9 enforces authentication and migrates its persistence engine from LokiJS to SQLite (`/store/wud.sqlite`). The plan configures Single Sign-On (SSO) using Authelia OIDC with automatic role mapping to the `admins` group, provides break-glass local admin fallback credentials, creates a persistent `./store:/store` volume mount, and updates the `/check-updates` automation skill to authenticate with a Personal API Token.

### Overall Assessment
The plan accurately identifies the primary architectural breaking changes of WUD v9. However, the Goldfish swarm uncovered critical implementation gaps:
1. A **circular dependency** in execution sequencing (skill modified before token generation).
2. Missing **Authelia OIDC client parameters** that would cause authentication/token exchange failure.
3. Silent failure when attempting to reload Authelia via `docker compose up -d`.
4. Missing **session persistence secret** (`WUD_AUTH_SESSION_SECRET`) causing forced session resets on restarts.
5. Inadequate directory permission handling for the SQLite mount.

---

## 2. Review Findings by Severity

### 🚨 Blocker Findings

#### B-1: Circular Step Dependency — Skill Modification Precedes Token Generation
* **Lenses:** `egm-implementation-readiness`, `egm-zoom-out`
* **Affected Scope:** Lines 89–90 (Step 4) & Lines 111–120 (Step 6)
* **Finding:**
  Step 4 instructs modifying `.claude/skills/check-updates/SKILL.md` to load and pass `WUD_API_TOKEN`. However, WUD v9 is not deployed until Step 5, and the token cannot physically exist until Step 6 (when an administrator logs into the newly running WUD UI). Modifying `SKILL.md` in Step 4 breaks existing skill invocations and cannot be verified.
* **Remediation:**
  Re-sequence execution steps:
  1. Step 4: Deploy & Verify WUD v9 Container.
  2. Step 5: Log in via Authelia SSO, generate Personal API Token, and save `WUD_API_TOKEN` to `infrastructure/wud/.env`.
  3. Step 6: Update `.claude/skills/check-updates/SKILL.md` and verify against live WUD v9.

#### B-2: Missing Authelia OIDC Client YAML Block & Incompatible Parameters
* **Lenses:** `egm-design`, `egm-codebase-details`, `egm-comprehension`
* **Affected Scope:** Lines 24–33 (Architecture Section 1) & Lines 68–73 (Step 2)
* **Finding:**
  The plan specifies high-level OIDC attributes but omits the concrete YAML snippet for `infrastructure/gateway/config/authelia/configuration.yml`. In Authelia 4.39:
  - WUD transmits client credentials in the HTTP `Authorization: Basic` header during code exchange (`token_endpoint_auth_method: 'client_secret_basic'`).
  - Authelia signs userinfo responses unless explicitly set to `userinfo_signed_response_alg: 'none'`, which WUD expects.
  - Peer services in this repo (like `audiobookshelf`) configure `require_pkce: true`. WUD v9 confidential client flow does not use PKCE; omitting `require_pkce: false` causes Authelia to reject requests.
  - Authelia requires explicit `response_types: ['code']` and `grant_types: ['authorization_code']`.
* **Remediation:**
  Provide the exact, copy-pasteable YAML block in the plan for `configuration.yml`:
  ```yaml
        - client_id: 'wud'
          client_name: "What's Up Docker"
          client_secret: '$pbkdf2-sha512$...' # Plaintext stored in infrastructure/wud/.env
          public: false
          authorization_policy: 'two_factor'
          require_pkce: false
          redirect_uris:
            - 'https://update.internal.pippinn.me/auth/oidc/authelia/cb'
          scopes:
            - 'openid'
            - 'profile'
            - 'email'
            - 'groups'
          response_types:
            - 'code'
          grant_types:
            - 'authorization_code'
          access_token_signed_response_alg: 'none'
          userinfo_signed_response_alg: 'none'
          token_endpoint_auth_method: 'client_secret_basic'
  ```

---

### ⚠️ Major Findings

#### M-1: Authelia Configuration Reload Silently Fails with `docker compose up -d`
* **Lenses:** `egm-codebase-details`, `egm-implementation-readiness`
* **Affected Scope:** Line 70–73 (Step 2.4) & Line 132 (Rollback)
* **Finding:**
  In `infrastructure/gateway/compose.yaml`, Authelia's configuration directory is mounted via host bind mount (`./config/authelia:/config`). Docker Compose only recreates containers if `compose.yaml` or declared environment variables change. Running `docker compose up -d authelia` after editing `configuration.yml` outputs `Container authelia Running` without restarting the process. Authelia will not load the new OIDC client.
* **Remediation:**
  Change command to restart explicitly:
  ```bash
  docker compose -f infrastructure/gateway/compose.yaml restart authelia
  ```

#### M-2: Missing `WUD_AUTH_SESSION_SECRET` Forces Session Expirations on Restart
* **Lenses:** `egm-design`, `egm-implementation-readiness`
* **Affected Scope:** Lines 38–50 & Lines 80–84
* **Finding:**
  WUD v9 uses session cookies for web UI sessions. If `WUD_AUTH_SESSION_SECRET` is unset, WUD derives an ephemeral secret from the app version and host MAC address on boot. Every container restart or update invalidates existing session cookies, terminating active logins. WUD requires this secret to be $\ge 32$ characters.
* **Remediation:**
  Add `WUD_AUTH_SESSION_SECRET` generation to Step 3:
  ```bash
  echo "WUD_AUTH_SESSION_SECRET=$(openssl rand -hex 32)" >> infrastructure/wud/.env
  ```

#### M-3: Missing Non-Root UID Ownership on Store Mount Causes Startup Crash
* **Lenses:** `egm-codebase-details`, `egm-design`, `egm-comprehension`, `egm-implementation-readiness`
* **Affected Scope:** Lines 76–79 (Step 3.1)
* **Finding:**
  The command `mkdir -p infrastructure/wud/store` leaves ownership as the executing user/root. The WUD container process runs as unprivileged user `node` (UID `1000:1000`), matching `PUID=1000` in `global.env`. If owned by root or restricted by umask, WUD crashes with `EACCES: permission denied, open '/store/wud.sqlite'`.
* **Remediation:**
  Specify explicit ownership and permission commands:
  ```bash
  mkdir -p infrastructure/wud/store
  chown -R 1000:1000 infrastructure/wud/store
  chmod 750 infrastructure/wud/store
  ```

#### M-4: Blanket `docker compose pull` Fails on Locally Built `autoupdater` Image
* **Lenses:** `egm-codebase-details`
* **Affected Scope:** Lines 98–101 (Step 5.2)
* **Finding:**
  The `infrastructure/wud` stack contains two services: `whatsupdocker` (`getwud/wud`) and `autoupdater` (`image: autoupdater:local`, `build: .`). Running `docker compose pull` attempts to pull `autoupdater:local` from Docker Hub, generating an image pull error.
* **Remediation:**
  Target the specific service:
  ```bash
  docker compose -f infrastructure/wud/compose.yaml pull whatsupdocker
  docker compose -f infrastructure/wud/compose.yaml up -d
  ```

#### M-5: Misplaced Claims Mapping Under Authelia IdP Configuration
* **Lenses:** `egm-zoom-out`
* **Affected Scope:** Line 32
* **Finding:**
  Line 32 specifies `- Claims: User mapped from preferred_username, groups claim mapped to groups.` under the Authelia OIDC client definition. Authelia does not support a `claims` mapping directive; claims are standard OIDC outputs of the requested scopes. Claims mapping is strictly a WUD client configuration setting (`WUD_AUTH_OIDC_AUTHELIA_USERNAMECLAIM` and `WUD_AUTH_OIDC_AUTHELIA_GROUPSCLAIM`).
* **Remediation:**
  Remove claims directive from the Authelia section and keep it strictly under WUD `vars.env`.

#### M-6: Missing Concrete File Diff Blocks for Implementation
* **Lenses:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 80–87, Lines 89–90
* **Finding:**
  The plan lacks exact replacement code for `vars.env`, `compose.yaml`, and `SKILL.md`.
* **Remediation:**
  Include verbatim code blocks in the plan so the implementer can apply exact diffs without ambiguity.

---

### 💡 Nit Findings

#### N-1: Non-Existent Variable `WUD_PUBLIC_URL`
* **Lenses:** `egm-design`
* **Affected Scope:** Line 39
* **Finding:** `WUD_PUBLIC_URL` is not consumed by WUD. WUD derives public base URLs from incoming reverse proxy headers (`Host`, `X-Forwarded-Proto`).
* **Remediation:** Remove `WUD_PUBLIC_URL` from `vars.env`.

#### N-2: Missing Explicit Traefik Loadbalancer Port
* **Lenses:** `egm-design`
* **Affected Scope:** `infrastructure/wud/compose.yaml`
* **Finding:** `compose.yaml` lacks `traefik.http.services.wud.loadbalancer.server.port=3000`. Relying on port auto-detection is fragile across major image bumps.
* **Remediation:** Add explicit port label to `compose.yaml`.

#### N-3: Standardize Working Directory and Commands from Repo Root
* **Lenses:** `egm-codebase-details`, `egm-implementation-readiness`
* **Affected Scope:** Lines 72, 100, 117
* **Finding:** Inconsistent `cd ~/homelab/...` vs relative paths.
* **Remediation:** Standardize all commands relative to repo root using `-f`.

#### N-4: Comprehensive Rollback Scope
* **Lenses:** `egm-implementation-readiness`, `egm-codebase-details`
* **Affected Scope:** Lines 123–132
* **Finding:** Rollback plan does not mention reverting `.claude/skills/check-updates/SKILL.md` or gitignored `./store`.
* **Remediation:** Include `git checkout` commands for all touched files and storage cleanup notes.

---

## 3. Recommended Remediation Plan

Update [`specs/28-wud-v9-upgrade/plan.md`](file:///Users/grimur/personal-code/homelab/specs/28-wud-v9-upgrade/plan.md) with:
1. Re-ordered 6-step execution sequence resolving the circular dependency.
2. Complete copy-pasteable Authelia OIDC client YAML block.
3. Explicit `docker compose -f ... restart authelia` command.
4. `WUD_AUTH_SESSION_SECRET` generation in `.env`.
5. `1000:1000` ownership and `750` permissions for `infrastructure/wud/store`.
6. Scoped `docker compose ... pull whatsupdocker` command.
7. Verbatim diffs for `compose.yaml`, `vars.env`, and `SKILL.md`.
8. Complete rollback commands.
