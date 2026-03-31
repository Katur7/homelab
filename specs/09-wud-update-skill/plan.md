# Spec 09: WUD Update Review Skill

## Goal

Create a Claude Code slash command skill (`/check-updates`) that:
1. Queries WUD at `https://update.internal.pippinn.me/api/containers`
2. Filters containers where `updateAvailable: true`
3. For each, fetches and summarises release notes between current and target version
4. Prominently flags breaking changes
5. Offers to apply the update (edit compose.yaml + restart container)

---

## Current State (WUD API observed 2026-03-30)

- **28 containers** monitored
- **5 pending updates:**

| Container | Current | Target | Semver Diff |
|-----------|---------|--------|-------------|
| cloudflare-ddns | 2.0.8 | 2.1.0 | minor |
| homeassistant | 2026.3.2 | 2026.3.4 | patch |
| matter-server | 6.2.2 | 8.1.0 | **MAJOR** |
| mealie | v3.13.1 | v3.14.0 | minor |
| qbittorrent | 5.1.4-r2-ls446 | 5.1.4-r2-ls447 | prerelease (ls-only) |

---

## Skill Location

**Project-level:** `.claude/commands/check-updates.md`

This keeps the skill version-controlled with the repo and available in all Claude Code
sessions opened in this working directory. It is NOT in `~/.claude/commands/` (global)
since it is homelab-specific.

**Invocation:** `/check-updates`

---

## Execution Flow

### Step 1 — Query WUD

```bash
curl -s https://update.internal.pippinn.me/api/containers \
  | jq '[.[] | select(.updateAvailable == true)]'
```

Extract per container:
- `name` — container name (used for `docker inspect` and `docker compose restart`)
- `image.name` — Docker image (used to resolve release notes URL)
- `updateKind.localValue` / `updateKind.remoteValue` — version range
- `updateKind.semverDiff` — major / minor / patch / prerelease
- `labels["com.docker.compose.project.config_files"]` — compose file path

---

### Step 2 — Resolve release notes URL

For each container needing an update:

1. **Primary:** `docker inspect <name>` → `Config.Labels["org.opencontainers.image.source"]`
2. **Secondary:** Match `image.name` against the static lookup table embedded in the skill (see below)

---

### Step 3 — Fetch release notes

**GitHub images** — use GitHub API for structured JSON:
```
GET https://api.github.com/repos/OWNER/REPO/releases?per_page=30
```
Filter to releases with tag between `localValue` and `remoteValue` (inclusive).

If `GITHUB_TOKEN` is set in the shell environment, include it as a Bearer token header
to raise the rate limit. Not required — unauthenticated limit (60/hr) is sufficient
for normal use. `GITHUB_TOKEN` is never committed; it lives only in the shell env.

**Home Assistant** — use the HA release blog:
```
WebSearch: site:home-assistant.io/blog "YYYY.M release"
WebFetch:  https://www.home-assistant.io/blog/YYYY/MM/DD/home-assistant-YYYY-M-release/
```
One fetch per HA version in the update range.

**Multi-release spans** — for containers jumping multiple versions (e.g. matter-server
6.2.2 → 8.1.0), fetch **all intermediate releases**, not just the final. Concatenate
and summarise collectively, calling out per-release breaking changes individually.

---

### Step 4 — Summarise

Output format per container:

```
## <Container Name>  <localValue> → <remoteValue>  [semverDiff]

### Releases covered
- [v8.1.0](<link>) — <one-line description>
- [v8.0.0](<link>) — <one-line description>  ⚠️ BREAKING
- [v7.x.x](<link>) — ...

### Summary
- Bullet 1
- Bullet 2
- Bullet 3

⚠️ BREAKING CHANGES
- ...
```

**Breaking change detection:**
- Always flag major version bumps (`semverDiff: "major"`)
- Scan release notes text for: "breaking", "breaking change", "migration required",
  "removed", "deprecated", "renamed", "must", "requires manual"
- Call out each release that contains a breaking change separately

**linuxserver `ls`-only bumps** (e.g. `ls446 → ls447`, app version unchanged):
- Print one line: `[container] — linuxserver base image update only (ls### bump). No upstream app changes.`
- Skip full release note fetch for these.
- Future milestone: investigate auto-updating ls-only / patch containers.

---

### Step 5 — Offer to update

After each container's summary, ask:

> Update **[container name]** to `[remoteValue]`? (y/n)

If **yes**:
1. **Detect version location:**
   - If `image:` line is a literal tag → edit that line in `compose.yaml`
   - If `image:` uses `${VAR:-default}` substitution → update `VAR` in `.env` instead
   - For immich: update both `immich-server` and `immich-machine-learning` together (shared `${IMMICH_VERSION}`)
2. **Pull the new image:**
   `docker compose -f <compose_file_path> pull <service_name>`
3. **Recreate the container:**
   `docker compose -f <compose_file_path> up -d --no-deps <service_name>`
   - Use `com.docker.compose.service` Docker label to get the compose service name (not container name)
4. **Verify:**
   - `docker inspect <container_name> --format '{{.State.Status}} {{.State.Health.Status}}'`
   - Wait up to 30s if a health check is configured; "running" is sufficient if none
5. Report result

If **no**: skip and move to the next container.

Process containers one at a time to allow review after each restart before proceeding.

**After all containers are processed:**
Remind the user to commit all changes:
> All updates applied. Run `/commit` to commit the compose.yaml changes.

---

## Release Notes URL Lookup Table

Embedded in the skill file. Used when OCI source label is absent or unhelpful.

| Image prefix | Release notes URL | Notes |
|---|---|---|
| `ghcr.io/home-assistant/home-assistant` | https://www.home-assistant.io/blog/ | Use HA blog, not GitHub |
| `ghcr.io/home-assistant-libs/python-matter-server` | https://github.com/home-assistant-libs/python-matter-server/releases | |
| `ghcr.io/advplyr/audiobookshelf` | https://github.com/advplyr/audiobookshelf/releases | |
| `vikunja/vikunja` | https://kolaente.dev/vikunja/vikunja/releases | Gitea, not GitHub |
| `ghcr.io/mealie-recipes/mealie` | https://github.com/mealie-recipes/mealie/releases | |
| `ghcr.io/immich-app/immich-server` | https://github.com/immich-app/immich/releases | immich-ml uses same repo |
| `ghcr.io/simjanos-dev/linguacafe-webserver` | https://github.com/simjanos-dev/LinguaCafe/releases | |
| `authelia/authelia` | https://github.com/authelia/authelia/releases | |
| `traefik` | https://github.com/traefik/traefik/releases | |
| `cloudflare/cloudflared` | https://github.com/cloudflare/cloudflared/releases | |
| `timothyjmiller/cloudflare-ddns` | https://github.com/timothyjmiller/cloudflare-ddns/releases | |
| `pihole/pihole` | https://github.com/pi-hole/pi-hole/releases | |
| `tailscale/tailscale` | https://github.com/tailscale/tailscale/releases | |
| `getwud/wud` | https://github.com/getwud/wud/releases | |
| `louislam/uptime-kuma` | https://github.com/louislam/uptime-kuma/releases | |
| `crowdsecurity/crowdsec` | https://github.com/crowdsecurity/crowdsec/releases | |
| `ghcr.io/lovelaze/nebula-sync` | https://github.com/lovelaze/nebula-sync/releases | |
| `wollomatic/socket-proxy` | https://github.com/wollomatic/socket-proxy/releases | |

### linuxserver.io images

For images under `ghcr.io/linuxserver/<app>` or `linuxserver/<app>`:
- Tag format: `APP_VERSION-ls###` (or `APP_VERSION-rN-ls###` for qbittorrent)
- If only `ls###` changed → skip full fetch; print one-line note
- If `APP_VERSION` changed → fetch **upstream app releases** (primary) + linuxserver docker releases (secondary)

| App | Upstream release URL | linuxserver docker URL |
|-----|---------------------|------------------------|
| radarr | https://github.com/Radarr/Radarr/releases | https://github.com/linuxserver/docker-radarr/releases |
| sonarr | https://github.com/Sonarr/Sonarr/releases | https://github.com/linuxserver/docker-sonarr/releases |
| prowlarr | https://github.com/Prowlarr/Prowlarr/releases | https://github.com/linuxserver/docker-prowlarr/releases |
| qbittorrent | https://github.com/qbittorrent/qBittorrent/releases | https://github.com/linuxserver/docker-qbittorrent/releases |
| plex | https://www.plex.tv/media-server-downloads/#plex-media-server | https://github.com/linuxserver/docker-plex/releases |
| calibre-web | https://github.com/janeczku/calibre-web/releases | https://github.com/linuxserver/docker-calibre-web/releases |
| syncthing | https://github.com/syncthing/syncthing/releases | https://github.com/linuxserver/docker-syncthing/releases |
| wireguard | https://github.com/WireGuard/wireguard-tools/releases | https://github.com/linuxserver/docker-wireguard/releases |

---

## Red Team Findings

Issues found during review, ordered by severity.

---

### 🔴 CRITICAL — Plan is wrong or will break

#### 1. Immich uses an env var for version, not a hardcoded tag

```yaml
image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-v2.6.1}
```

Editing the `image:` line to a hardcoded tag would break the env var pattern. The update
must target `IMMICH_VERSION` in `services/immich/.env`, not `compose.yaml`.

Additionally, `immich-machine-learning` uses the same `${IMMICH_VERSION}` but has
`wud.watch=false` — so WUD only reports `immich-server`. Updating immich-server without
also updating immich-machine-learning to the same version is unsupported by Immich and
can cause subtle failures. The skill must treat immich as a coupled pair.

**Fix:** Detect env var substitution in the image tag. When present, update the variable
in `.env` rather than the compose line. For coupled services (same version var), restart
all services in the compose file that share that variable.

#### 2. New image won't pull without an explicit pull step

`docker compose up -d --no-deps <service>` does NOT pull the new image tag by default if
Docker has any local cache. Without pulling first, the container will recreate using
whatever is locally cached under that tag (possibly nothing, which is an error).

**Fix:** Add `docker compose pull <service>` before `up -d`, or use `--pull always` flag.

#### 3. HA patch releases don't have blog posts

`home-assistant.io/blog/` only publishes posts for the monthly `.1` release. Patch
releases (`2026.3.2`, `2026.3.4`, etc.) have no dedicated blog post — only a GitHub
release entry listing bug fixes.

**Fix:** For HA, check the version suffix: if it ends in `.1`, use the blog; for `.2+`
patch releases, fall back to `https://github.com/home-assistant/core/releases/tag/YYYY.M.N`.

---

### 🟡 MODERATE — Correctness issues or gaps

#### 4. matter-server: large version gap will be slow and context-heavy

6.2.2 → 8.1.0 could span 20+ individual releases. Fetching, reading, and summarising
each one individually will be very slow and burns a lot of context window.

**Decision:** Accept this risk. Large version gaps are unusual. If it becomes a problem
in practice, address it then.

#### 5. GitHub API `per_page=30` misses releases for large version gaps

Same problem as above from the API side.

**Decision:** Same as #4 — handle if it happens.

#### 6. GitHub release tag format vs WUD version format

WUD `remoteValue`/`localValue` may or may not include a `v` prefix depending on the
image. GitHub tags also vary. Examples:
- mealie WUD: `v3.14.0` → GitHub tag: `v3.14.0` ✓
- matter-server WUD: `8.1.0` → GitHub tag: `v8.1.0` (with `v`)
- HA WUD: `2026.3.4` → GitHub tag: `2026.3.4` (no `v`)

Strict string matching will miss releases.

**Fix:** When searching GitHub releases, normalise by stripping/adding `v` prefix and
compare both forms.

#### 7. Vikunja release notes are on Gitea, not GitHub

`kolaente.dev/vikunja/vikunja/releases` is a self-hosted Gitea instance. The GitHub API
approach doesn't apply. The Gitea API exists (`/api/v1/repos/...`) but may require auth.

**Fix:** For vikunja, use WebFetch of the HTML releases page. Note this in the lookup
table as "Gitea — HTML fetch only."

#### 8. No git commit step after update

Per the GitOps-lite principle in AI_INSTRUCTIONS.md, all changes to compose.yaml (or
`.env`) should be committed. The plan currently ends at "restart container" with no
version control step.

**Decision:** Group all update commits into a single commit at the end of the session
(after all containers have been processed), rather than committing after each one.
The skill should remind the user to commit at the end.

#### 9. `docker ps` only confirms "running", not "healthy"

Some containers have health checks (e.g. vikunja waits for postgres `service_healthy`).
A container can be "running" but in "starting" or "unhealthy" state.

**Fix:** After restart, check `docker inspect <name> --format '{{.State.Health.Status}}'`.
If health check is not configured, "running" is sufficient. Wait up to ~30s for health.

#### 10. postgres (vikunja-db) is WUD-watched — no lookup entry, no DB warning

`vikunja-db` uses `postgres:17` with `wud.tag.include=^\d+\.\d+$` so WUD reports it.
The lookup table has no entry, and database updates carry extra risk.

**Decision:** Add `wud.watch=false` to `vikunja-db` in `services/vikunja/compose.yaml`.
Postgres major version upgrades require a data migration (`pg_upgrade`) and should never
be done casually from a skill. Remove it from WUD's scope entirely.

---

### 🟢 MINOR — Polish / future-proofing

#### 11. `it-tools` missing from lookup table and WUD not watching it

`corentinth/it-tools:2024.10.22-7ca5933` — already pinned to the latest release tag
(date-hash format, no semver). No `wud.tag.include` label so WUD can't detect updates.

**Decision:** Add `wud.tag.include=^\d{4}\.\d{2}\.\d{2}-[a-f0-9]{7}$` label to
`services/it-tools/compose.yaml`. Add to the skill lookup table:
`https://github.com/CorentinTh/it-tools/releases`.

#### 12. Service name vs container name for `docker compose up`

`docker compose up -d --no-deps <name>` takes the **service name** (from compose YAML),
not the container name. For most stacks they match, but they can diverge (e.g.
`container_name: immich_server` vs service name `immich-server`).

**Fix:** Extract the service name from the `com.docker.compose.service` Docker label
(set automatically by Compose), not from the WUD container name.

#### 13. "Future auto-update" note may set expectations

The ls-only note "Future milestone: investigate auto-update" is aspirational but
unplanned. Leave it as a user comment, not a formal milestone reference.

---

## Decisions Made

| # | Decision |
|---|----------|
| 1 | No `GITHUB_TOKEN` required. Mention in skill as optional if rate limiting occurs. |
| 2 | ls-only linuxserver bumps: skip with one-line note. May revisit auto-update later. |
| 3 | Multi-version spans: fetch ALL intermediate releases. |
| 4 | HA release notes: use HA blog for `.1` monthly releases; GitHub for `.2+` patches. Aggressively summarise. Link per release. |
| 5 | Per-container ask → edit compose.yaml or `.env` → pull → restart. Commit compose.yaml changes grouped at end (`.env` is gitignored, never committed). |
| RT-1 | Immich: detect `${VAR}` substitution and update `.env`; update server + ML together. |
| RT-2 | Add `--pull` step before `docker compose up -d`. |
| RT-3 | HA patch releases fall back to GitHub release page. |
| RT-4/5 | Large version gaps / pagination: accept risk, handle if it happens. |
| RT-6 | Normalise `v` prefix when matching WUD versions to GitHub release tags. |
| RT-7 | Vikunja Gitea: HTML WebFetch only, note in lookup table. |
| RT-8 | Group all update commits at end; skill reminds user to run `/commit`. |
| RT-9 | Check container health status post-restart, not just running state. |
| RT-10 | Add `wud.watch=false` to `vikunja-db` — postgres major upgrades require manual migration. |
| RT-11 | Add `wud.tag.include` regex to `it-tools`; add to lookup table. |
| RT-12 | Use `com.docker.compose.service` label for compose service name, not WUD container name. |
| RT-13 | Remove aspirational "future milestone" auto-update note from skill text. |

---

## Rollback / Risk

- Skill reads are non-destructive.
- Updates are applied one container at a time with confirmation.
- Rollback for a bad update: revert the `image:` tag in compose.yaml and re-run `docker compose up -d --no-deps <service>`.

---

## Pre-work (compose changes required before skill is useful)

These changes are made as part of this milestone, before writing the skill:

1. `services/vikunja/compose.yaml` — add `wud.watch=false` to `vikunja-db`
2. `services/it-tools/compose.yaml` — add `wud.tag.include=^\d{4}\.\d{2}\.\d{2}-[a-f0-9]{7}$` label

---

## Out of Scope

- Watching Pi-hosted containers (WUD only runs on NAS)
- Auto-update without confirmation
- Batch updating all containers in one command
- Postgres / database image upgrades (excluded via `wud.watch=false`)
