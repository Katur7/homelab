# AI Agent Instructions

When modifying or generating configurations in this repository, you **MUST** adhere to these rules:

### 1. File Naming & Syntax
- Use `compose.yaml`, NOT `docker-compose.yml`.
- Use Traefik v3 syntax for labels. Example: `Host(`service.pippinn.me`)`.
- Pin images to specific versions. Do NOT use `:latest`.

### 2. Secrets Handling
- NEVER place passwords or API keys in `compose.yaml` or `vars.env`.
- Place secrets in `.env` and reference them as variables `${SECRET_NAME}`.

### 3. Validation Steps
- Before suggesting a final YAML, run `docker compose config` to verify syntax.
- Ensure `depends_on` includes `condition: service_healthy` for database dependencies.

### 4. Immich Specifics
- Immich OIDC handshake requires bypass for: `/.well-known/immich` and `/api/oauth/mobile-redirect`.
- Use header secrets for the mobile app to bypass Authelia.