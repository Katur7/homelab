---
name: check-updates
description: Check WUD for pending container updates, summarise release notes, highlight breaking changes, and offer to apply each update.
allowed-tools: WebFetch, WebSearch, Read, AskUserQuestion
---

# /check-updates — WUD Container Update Review

Check What's Up Docker for pending container updates, summarise release notes, highlight breaking changes, and offer to apply each update.

---

## Step 1 — Query WUD

Run:
```bash
curl -s https://update.internal.pippinn.me/api/containers | jq '[.[] | select(.updateAvailable == true)]'
```

If the curl fails (WUD unreachable), stop and report the error clearly.

If the result is an empty array, report "No updates available." and stop.

For each container needing an update, extract:
- `name` — container name
- `image.name` — Docker image reference (e.g. `ghcr.io/mealie-recipes/mealie`)
- `updateKind.localValue` — current version
- `updateKind.remoteValue` — available version
- `updateKind.semverDiff` — `major` / `minor` / `patch` / `prerelease`
- `labels["com.docker.compose.project.config_files"]` — absolute path to compose.yaml

---

## Step 2 — Resolve release notes URL

For each container:

1. **Primary:** Run `docker inspect <name> --format '{{index .Config.Labels "org.opencontainers.image.source"}}'`. Use the result if it is a valid GitHub/Gitea URL.
2. **Secondary:** Match `image.name` against the lookup table below.

### Lookup Table

| Image prefix | Release notes URL | Notes |
|---|---|---|
| `ghcr.io/home-assistant/home-assistant` | https://www.home-assistant.io/blog/ | See HA handling below |
| `ghcr.io/home-assistant-libs/python-matter-server` | https://github.com/home-assistant-libs/python-matter-server/releases | GitHub API |
| `ghcr.io/advplyr/audiobookshelf` | https://github.com/advplyr/audiobookshelf/releases | GitHub API |
| `vikunja/vikunja` | https://kolaente.dev/vikunja/vikunja/releases | Gitea — HTML WebFetch only |
| `ghcr.io/mealie-recipes/mealie` | https://github.com/mealie-recipes/mealie/releases | GitHub API |
| `ghcr.io/immich-app/immich-server` | https://github.com/immich-app/immich/releases | GitHub API |
| `ghcr.io/simjanos-dev/linguacafe-webserver` | https://github.com/simjanos-dev/LinguaCafe/releases | GitHub API |
| `authelia/authelia` | https://github.com/authelia/authelia/releases | GitHub API |
| `traefik` | https://github.com/traefik/traefik/releases | GitHub API |
| `cloudflare/cloudflared` | https://github.com/cloudflare/cloudflared/releases | GitHub API |
| `timothyjmiller/cloudflare-ddns` | https://github.com/timothymiller/cloudflare-ddns/releases | GitHub API — DockerHub image is `timothyjmiller/` but GitHub repo owner is `timothymiller/` (no j); OCI label resolves this correctly |
| `pihole/pihole` | https://github.com/pi-hole/pi-hole/releases | GitHub API |
| `tailscale/tailscale` | https://github.com/tailscale/tailscale/releases | GitHub API |
| `getwud/wud` | https://github.com/getwud/wud/releases | GitHub API |
| `louislam/uptime-kuma` | https://github.com/louislam/uptime-kuma/releases | GitHub API |
| `crowdsecurity/crowdsec` | https://github.com/crowdsecurity/crowdsec/releases | GitHub API |
| `ghcr.io/lovelaze/nebula-sync` | https://github.com/lovelaze/nebula-sync/releases | GitHub API |
| `wollomatic/socket-proxy` | https://github.com/wollomatic/socket-proxy/releases | GitHub API |
| `corentinth/it-tools` | https://github.com/CorentinTh/it-tools/releases | GitHub API |

### linuxserver.io images

Tag format: `APP_VERSION-ls###` or `APP_VERSION-rN-ls###`

- **If only `ls###` changed** (app version unchanged): print one line — `[container] — linuxserver base image / security update only (ls### bump). No upstream app changes.` — then **skip to the next container**. Do not fetch release notes.
- **If app version changed**: fetch upstream app releases (primary) AND linuxserver docker releases (secondary).

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

## Step 3 — Fetch release notes

### GitHub images

Use the GitHub API:
```
GET https://api.github.com/repos/OWNER/REPO/releases?per_page=30
```

If `GITHUB_TOKEN` is set in the shell environment, pass it as a header:
```
Authorization: Bearer $GITHUB_TOKEN
```
(Not required. Unauthenticated limit is 60 requests/hour, sufficient for normal use.)

Filter the returned releases to those whose tag falls **between `localValue` and `remoteValue` inclusive**. When matching tags, normalise the `v` prefix — compare both `v1.2.3` and `1.2.3` forms against the WUD version string.

For containers jumping **multiple versions** (e.g. `semverDiff: "major"` or a large gap), fetch **all intermediate releases**, not just the latest.

### Home Assistant

HA version format: `YYYY.M.N`

- **Monthly release** (`.N` = 1, e.g. `2026.3.1`): Use the blog post.
  - WebSearch: `site:home-assistant.io/blog "YYYY.M release"` to find the URL.
  - WebFetch the blog post. Aggressively summarise — extract headers and key bullet points only.
- **Patch release** (`.N` ≥ 2, e.g. `2026.3.4`): Use GitHub.
  - `GET https://api.github.com/repos/home-assistant/core/releases/tags/YYYY.M.N`

If the update spans both a monthly and patch releases, handle each appropriately.

### Vikunja (Gitea)

WebFetch `https://kolaente.dev/vikunja/vikunja/releases` and extract the relevant version entries from the HTML. The Gitea API may require authentication — use WebFetch of the HTML page instead.

---

## Step 4 — Summarise

Process **one container at a time**. Output format:

```
## [Container Name]  localValue → remoteValue  (semverDiff)

### Releases covered
- [vX.Y.Z](release-url) — one-line description
- [vX.Y.Z](release-url) — one-line description  ⚠️ BREAKING

### Summary
- Key change 1
- Key change 2
- Key change 3

⚠️ BREAKING CHANGES
- Specific breaking change with migration note
```

**Breaking change detection — always flag:**
- Any container with `semverDiff: "major"`
- Release notes containing: "breaking", "breaking change", "migration required", "removed", "deprecated", "renamed", "must", "requires manual"
- List each affected release individually under the breaking changes block

**If no breaking changes:** omit the `⚠️ BREAKING CHANGES` block entirely.

Then proceed to Step 5 for this container before moving to the next.

---

## Step 5 — Offer to update

After each container's summary, use the `AskUserQuestion` tool to present the choice as buttons:
- Question: `Update [container] from localValue to remoteValue?`
- Options: `["Yes — apply update", "No — skip"]`

### If yes:

**1. Locate the compose file**

The compose file path comes from the `com.docker.compose.project.config_files` Docker label (already extracted in Step 1).

**2. Detect where the version is stored**

Read the `image:` line in the compose file:
- **Hardcoded tag** (e.g. `image: ghcr.io/mealie-recipes/mealie:v3.13.1`) → edit that line in `compose.yaml` directly.
- **Env var substitution** (e.g. `image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-v2.6.1}`) → update the variable in the stack's `.env` file instead. **Never commit `.env` files.**

**3. Pull new images**
```bash
docker compose -f <compose_file_path> pull
```

**4. Recreate updated containers**
```bash
docker compose -f <compose_file_path> up -d
```
This only recreates containers whose image or config changed — coupled services (e.g. immich-server + immich-machine-learning sharing `${IMMICH_VERSION}`) are handled automatically.

**5. Verify**
```bash
docker inspect <container_name> --format '{{.State.Status}} {{.State.Health.Status}}'
```
- If a health check is configured: wait up to 30 seconds for `healthy`. Report clearly if it does not reach healthy.
- If no health check: `running` is sufficient.

Report the result before moving to the next container.

### If no:

Skip and move to the next container.

---

## After all containers are processed

Remind the user:

> All updates applied. Run `/commit` to commit the compose.yaml changes.

Note: `.env` files are gitignored and are never committed. If a version was updated only in `.env` (e.g. a container using `${VAR}` substitution), there will be no compose.yaml change to commit for that container — mention this explicitly.
