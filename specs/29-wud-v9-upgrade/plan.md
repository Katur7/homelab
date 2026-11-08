# Milestone 29: What's Up Docker (WUD) v9 Upgrade & Authentication Hardening

## 📌 Context & Objectives

What's Up Docker (WUD) on the NAS (`infrastructure/wud`) is currently running `getwud/wud:8.4.0` with unauthenticated web UI access over internal Traefik (`https://update.internal.pippinn.me`).

WUD v9 introduces significant architectural and security breaking changes:
1. **Mandatory Authentication:** Anonymous access is removed. The container fails fast on startup if no administrator is provisioned.
2. **Persistence Migration (LokiJS → SQLite):** Internal storage shifted from LokiJS to SQLite managed via Drizzle ORM (`/store/wud.sqlite`). Requires a persistent storage mount (`/store`) so users, sessions, container states, and API tokens survive container restarts.
3. **Role-Based Access Control (RBAC):** Native support for `admin`, `rw`, and `ro` roles with user management in the UI.
4. **REST API Lockdown:** Endpoints such as `/api/containers` now reject unauthenticated calls with HTTP 401 Unauthorized, impacting automation tools like the `/check-updates` skill.

**Goals:**
- Upgrade WUD from `8.4.0` to `9.7.0`.
- Integrate single sign-on (SSO) using Authelia OIDC with automatic role mapping to the `admins` group.
- Provide break-glass local administrator credentials via `.env`.
- Add persistent SQLite storage mount (`./store:/store`) with `1000:1000` ownership, gitignored, and backed up by Borg.
- Set a stable cryptographic `WUD_AUTH_SESSION_SECRET` to prevent session invalidation on restart.
- Update `.claude/skills/check-updates/SKILL.md` to authenticate requests with a Personal API Token loaded from `infrastructure/wud/.env`.

---

## 🛠️ Architecture & Decisions

### 1. Authelia OIDC Client
Add WUD as a registered OpenID Connect client in `infrastructure/gateway/config/authelia/configuration.yml`:
- **Client ID:** `wud`
- **Client Name:** `What's Up Docker`
- **Client Secret:** Hashed secret stored in Authelia configuration; plaintext secret stored in `infrastructure/wud/.env` (gitignored).
- **Authorization Policy:** `two_factor`
- **Redirect URIs:** `https://update.internal.pippinn.me/auth/oidc/authelia/cb`
- **Scopes:** `openid`, `profile`, `email`, `groups`
- **Authentication Method:** `client_secret_basic` (WUD transmits credentials via HTTP Basic header).
- **PKCE:** `require_pkce: false` (WUD confidential client flow does not use PKCE).
- **Response & Grant Types:** `code` / `authorization_code`.
- **Userinfo Response:** `userinfo_signed_response_alg: 'none'` (WUD expects standard JSON claims response).

Exact Authelia client configuration block:
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

### 2. WUD Service Configuration (`infrastructure/wud`)
- **Image:** `getwud/wud:9.7.0` (pinned, no `:latest`).
- **Volume:** `./store:/store` (persists `wud.sqlite`, owned by `1000:1000`).
- **Traefik Router:** Keep existing `websecure` internal router with global `internal-only` IP allowlist. Add explicit service port label `traefik.http.services.wud.loadbalancer.server.port=3000`. Do not apply `authelia-auth@file` forward-auth (WUD handles authentication natively; forward-auth would break API token calls).
- **Environment Variables (`vars.env`):**
  ```env
  # OIDC Single Sign-On (Authelia)
  WUD_AUTH_OIDC_AUTHELIA_CLIENTID=wud
  WUD_AUTH_OIDC_AUTHELIA_DISCOVERY=https://auth.pippinn.me/.well-known/openid-configuration
  WUD_AUTH_OIDC_AUTHELIA_GROUPSCLAIM=groups
  WUD_AUTH_OIDC_AUTHELIA_ADMINGROUP=admins
  WUD_AUTH_OIDC_AUTHELIA_USERNAMECLAIM=preferred_username
  ```
- **Secrets (`.env` - gitignored):**
  - `WUD_AUTH_ADMIN_USER`: Break-glass local admin username.
  - `WUD_AUTH_ADMIN_PASSWORD`: Break-glass local admin password.
  - `WUD_AUTH_OIDC_AUTHELIA_CLIENTSECRET`: Authelia OIDC plaintext client secret.
  - `WUD_AUTH_SESSION_SECRET`: Stable 32-byte hex string for session cookie encryption.
  - `WUD_API_TOKEN`: Personal API token generated post-deployment for script/skill automation (consumed strictly by host automation, not by WUD runtime).

### 3. Data Integrity & Backup Strategy
- SQLite database resides at `infrastructure/wud/store/wud.sqlite`.
- Path `/infrastructure/wud/store/` is added to `.gitignore`.
- Backed up daily to Borg repository via `infrastructure/backup/backup-local.sh` (`homelab/` backup source).
- WUD operates with low write churn; container state can also be reconstructed on demand from Docker socket labels.

---

## 📋 Execution Steps

All commands run from the repository root (`/home/grimur/homelab`).

### Step 1: Update `.gitignore`
Add `/infrastructure/wud/store/` to `.gitignore` under `# Service state`:
```diff
--- a/.gitignore
+++ b/.gitignore
@@ -21,3 +21,4 @@ volumes/
 /services/audiobookshelf/metadata/
 /services/home-assistant/config/*
 !/services/home-assistant/config/configuration.yaml
 !/services/home-assistant/config/packages/
+/infrastructure/wud/store/
```

### Step 2: Register OIDC Client in Authelia
1. Generate PBKDF2 hash for a random client secret:
   ```bash
   docker run --rm authelia/authelia:4.39 authelia crypto hash generate pbkdf2 --variant sha512 --random-salt
   ```
2. Insert the client block into `infrastructure/gateway/config/authelia/configuration.yml` under `identity_providers.oidc.clients`:
   ```yaml
         - client_id: 'wud'
           client_name: "What's Up Docker"
           client_secret: '<GENERATED_PBKDF2_HASH>'
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
3. Restart Authelia to reload configuration (Compose `up -d` does not reload bind-mount edits):
   ```bash
   docker compose -f infrastructure/gateway/compose.yaml restart authelia
   ```
4. Record the plaintext client secret in `infrastructure/wud/.env`:
   ```bash
   echo "WUD_AUTH_OIDC_AUTHELIA_CLIENTSECRET=<PLAINTEXT_SECRET>" >> infrastructure/wud/.env
   ```

### Step 3: Configure WUD Storage, Environment & Compose
1. Create storage directory with `1000:1000` ownership and `750` permissions:
   ```bash
   mkdir -p infrastructure/wud/store
   chown -R 1000:1000 infrastructure/wud/store
   chmod 750 infrastructure/wud/store
   ```
2. Append OIDC settings to `infrastructure/wud/vars.env`:
   ```env
   # OIDC Single Sign-On (Authelia)
   WUD_AUTH_OIDC_AUTHELIA_CLIENTID=wud
   WUD_AUTH_OIDC_AUTHELIA_DISCOVERY=https://auth.pippinn.me/.well-known/openid-configuration
   WUD_AUTH_OIDC_AUTHELIA_GROUPSCLAIM=groups
   WUD_AUTH_OIDC_AUTHELIA_ADMINGROUP=admins
   WUD_AUTH_OIDC_AUTHELIA_USERNAMECLAIM=preferred_username
   ```
3. Generate session secret and bootstrap admin credentials in `infrastructure/wud/.env`:
   ```bash
   echo "WUD_AUTH_SESSION_SECRET=$(openssl rand -hex 32)" >> infrastructure/wud/.env
   echo "WUD_AUTH_ADMIN_USER=admin" >> infrastructure/wud/.env
   echo "WUD_AUTH_ADMIN_PASSWORD=$(openssl rand -base64 24)" >> infrastructure/wud/.env
   ```
4. Update `infrastructure/wud/compose.yaml`:
   - Bump `image: getwud/wud:8.4.0` → `image: getwud/wud:9.7.0`
   - Add volume mount `- ./store:/store`
   - Add label `- "traefik.http.services.wud.loadbalancer.server.port=3000"`

   ```yaml
     whatsupdocker:
       image: getwud/wud:9.7.0
       container_name: update
       env_file:
         - ../../global.env
         - vars.env
         - .env
       volumes:
         - ./store:/store
       networks:
         - traefik_internal
         - socket_proxy
         - wud_internal
       labels:
         - "wud.autoupdate=true"
         - "traefik.enable=true"
         - "traefik.http.routers.wud.entrypoints=websecure"
         - "traefik.http.routers.wud.rule=Host(`update.internal.pippinn.me`)"
         - "traefik.http.services.wud.loadbalancer.server.port=3000"
         - "traefik.docker.network=traefik_internal"
       restart: unless-stopped
   ```

### Step 4: Deploy & Verify WUD v9
1. Validate compose configurations:
   ```bash
   docker compose -f infrastructure/gateway/compose.yaml config
   docker compose -f infrastructure/wud/compose.yaml config
   ```
2. Pull updated WUD image (explicitly targeting `whatsupdocker` to avoid pulling local `autoupdater` image) and recreate container:
   ```bash
   docker compose -f infrastructure/wud/compose.yaml pull whatsupdocker
   docker compose -f infrastructure/wud/compose.yaml up -d whatsupdocker
   ```
3. Inspect container startup and SQLite initialization:
   ```bash
   docker logs -f update
   ```
   Verify logs confirm:
   - Database migrations applied to `/store/wud.sqlite`.
   - OIDC provider `authelia` registered successfully.
   - HTTP server listening on port 3000.
4. Test Web UI at `https://update.internal.pippinn.me`:
   - Click "Sign in with Authelia" (or confirm automatic redirect).
   - Authenticate with Authelia passkey/2FA.
   - Verify user receives `admin` role from `admins` group membership.
   - Verify local admin login works using credentials generated in `infrastructure/wud/.env`.

### Step 5: Generate Personal API Token
1. In WUD Web UI, open User Profile menu (`Profile > API Tokens` or `Configuration > Users`).
2. Generate a Personal API Token named `check-updates` with `read` scope.
3. Append token to `infrastructure/wud/.env`:
   ```bash
   echo "WUD_API_TOKEN=<GENERATED_TOKEN>" >> infrastructure/wud/.env
   ```
4. Test REST API query:
   ```bash
   TOKEN=$(grep -E '^WUD_API_TOKEN=' infrastructure/wud/.env | cut -d= -f2-)
   curl -s -H "Authorization: Bearer $TOKEN" https://update.internal.pippinn.me/api/containers | jq .
   ```

### Step 6: Update `/check-updates` Skill
Modify `.claude/skills/check-updates/SKILL.md` (lines 15–20) to extract `WUD_API_TOKEN` and pass the Authorization header:

```diff
--- a/.claude/skills/check-updates/SKILL.md
+++ b/.claude/skills/check-updates/SKILL.md
@@ -14,5 +14,8 @@ Check What's Up Docker for pending container updates, summarise release notes, h
 ## Step 1 — Query WUD
 
 Run:
 ```bash
-curl -s https://update.internal.pippinn.me/api/containers | jq '[.[] | select(.updateAvailable == true)]'
+TOKEN=$(grep -E '^WUD_API_TOKEN=' infrastructure/wud/.env | cut -d= -f2-)
+curl -s -H "Authorization: Bearer $TOKEN" https://update.internal.pippinn.me/api/containers | jq '[.[] | select(.updateAvailable == true)]'
 ```
```

Test skill invocation to confirm updates are discovered without 401 Unauthorized errors.

---

## 🔄 Rollback Plan

If WUD v9 fails to start or authentication issues cannot be resolved:
1. Revert repository files:
   ```bash
   git checkout -- infrastructure/wud/compose.yaml infrastructure/wud/vars.env .claude/skills/check-updates/SKILL.md .gitignore
   ```
2. Remove OIDC client entry from `infrastructure/gateway/config/authelia/configuration.yml` and restart Authelia:
   ```bash
   git checkout -- infrastructure/gateway/config/authelia/configuration.yml
   docker compose -f infrastructure/gateway/compose.yaml restart authelia
   ```
3. Recreate WUD with previous 8.4.0 image:
   ```bash
   docker compose -f infrastructure/wud/compose.yaml up -d --force-recreate whatsupdocker
   ```
4. Clean up SQLite store if rolling back permanently:
   ```bash
   rm -rf infrastructure/wud/store
   ```
