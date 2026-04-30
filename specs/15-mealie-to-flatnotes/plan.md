# Milestone 15: Replace Mealie with Flatnotes

## Goal
Replace Mealie (recipe manager, ~150-300 MB idle) with Flatnotes (markdown note app, ~20 MB idle).
Use case: occasional recipe storage and browsing. No meal planning, shopping lists, or nutritional tracking required.

## What We Lose
- URL-based recipe scraping
- Ingredient scaling
- Shopping list generation
- Cook mode
- Multi-user roles

## What We Keep
- Recipe storage and browsing via web UI
- Markdown editing
- Search and tagging
- Internal-only access via Traefik

---

## Steps

### 1. Deploy Flatnotes
- Create `services/flatnotes/` with `compose.yaml` and `vars.env`.
- Domain: `recipes.pippinn.me` (externally accessible, consistent with audiobookshelf/vikunja pattern).
- Two Traefik routers:
  - `flatnotes-internal` on `websecure` entrypoint — LAN-only (IP restricted by global middleware)
  - `flatnotes-tunnel` on `tunnel` entrypoint — Authelia gated (`authelia-auth@file`)
- Auth: `FLATNOTES_AUTH_TYPE=NONE` — Authelia is the sole gatekeeper. No Flatnotes credentials needed.
- Data volume: `./data` mounted to `/app/data` (plain `.md` files, easy to inspect/backup).
- WUD autoupdate label included.
- Memory cap: 128 MB (conservative).

### 2. Verify Flatnotes
- Browse, edit, and create a test recipe.
- Confirm search and tagging work.
- Confirm Traefik routing resolves correctly.

### 3. Add DNS entry
- Run `./scripts/add-dns.sh recipes` to create `recipes.pippinn.me` → NAS IP in Pi-hole.

### 4. Tear down Mealie
- `docker compose down` in `services/mealie/`.
- Remove `services/mealie/` directory (no data to preserve — zero recipes).
- No DNS entry to clean up (`mealie.internal.pippinn.me` is Pi-hole local DNS — remove via Pi-hole UI or API).

---

## Rollback
- Mealie data volume is intact until step 4 — can `docker compose up` to restore immediately.
- Mealie image is pinned (`v3.16.0`) so rollback is deterministic.

---

## Impact on Other Services
- None. Mealie has no dependencies from other services.
- Traefik: old router `mealie` removed, new router `flatnotes` added — no conflict.

## New Secrets Required
None. `FLATNOTES_AUTH_TYPE=NONE` — Authelia handles authentication entirely.

## Notes
- On the LAN (`websecure`), Flatnotes is open to anyone on the network (IP restricted by Traefik's global `internal-only` middleware). Recipes are low-sensitivity — acceptable.
- Authelia access control rules do not require per-service changes; `authelia-auth@file` middleware handles it at the Traefik layer.
