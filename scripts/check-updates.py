#!/usr/bin/env python3
"""
CLI script to query WUD for pending container updates, resolve source repositories,
fetch release notes between local and remote versions, detect breaking changes,
and output structured JSON or a human-readable Markdown report.
"""

import argparse
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

WUD_URL = os.environ.get("WUD_URL", "https://update.internal.pippinn.me/api/containers")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "User-Agent": "homelab-check-updates/1.0",
}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"Bearer {GITHUB_TOKEN}"

# Static lookup table for image names to GitHub / Gitea repo
STATIC_REPO_LOOKUP: Dict[str, Tuple[str, str]] = {
    "ghcr.io/home-assistant/home-assistant": ("github", "home-assistant/core"),
    "homeassistant/home-assistant": ("github", "home-assistant/core"),
    "ghcr.io/home-assistant-libs/python-matter-server": ("github", "home-assistant-libs/python-matter-server"),
    "ghcr.io/advplyr/audiobookshelf": ("github", "advplyr/audiobookshelf"),
    "vikunja/vikunja": ("github", "go-vikunja/vikunja"),
    "ghcr.io/mealie-recipes/mealie": ("github", "mealie-recipes/mealie"),
    "ghcr.io/immich-app/immich-server": ("github", "immich-app/immich"),
    "ghcr.io/simjanos-dev/linguacafe-webserver": ("github", "simjanos-dev/LinguaCafe"),
    "authelia/authelia": ("github", "authelia/authelia"),
    "traefik": ("github", "traefik/traefik"),
    "cloudflare/cloudflared": ("github", "cloudflare/cloudflared"),
    "timothyjmiller/cloudflare-ddns": ("github", "timothymiller/cloudflare-ddns"),
    "timothymiller/cloudflare-ddns": ("github", "timothymiller/cloudflare-ddns"),
    "pihole/pihole": ("github", "pi-hole/docker-pi-hole"),
    "tailscale/tailscale": ("github", "tailscale/tailscale"),
    "getwud/wud": ("github", "getwud/wud"),
    "louislam/uptime-kuma": ("github", "louislam/uptime-kuma"),
    "crowdsecurity/crowdsec": ("github", "crowdsecurity/crowdsec"),
    "ghcr.io/lovelaze/nebula-sync": ("github", "lovelaze/nebula-sync"),
    "wollomatic/socket-proxy": ("github", "wollomatic/socket-proxy"),
    "corentinth/it-tools": ("github", "CorentinTh/it-tools"),
}

LINUXSERVER_UPSTREAM: Dict[str, Tuple[Optional[str], str]] = {
    "radarr": ("Radarr/Radarr", "linuxserver/docker-radarr"),
    "sonarr": ("Sonarr/Sonarr", "linuxserver/docker-sonarr"),
    "prowlarr": ("Prowlarr/Prowlarr", "linuxserver/docker-prowlarr"),
    "qbittorrent": ("qbittorrent/qBittorrent", "linuxserver/docker-qbittorrent"),
    "plex": (None, "linuxserver/docker-plex"),
    "calibre-web": ("janeczku/calibre-web", "linuxserver/docker-calibre-web"),
    "syncthing": ("syncthing/syncthing", "linuxserver/docker-syncthing"),
    "wireguard": ("WireGuard/wireguard-tools", "linuxserver/docker-wireguard"),
}

BREAKING_PATTERNS = re.compile(
    r"\b(breaking(\s+change[s]?)?|migration(\s+required)?|deprecated|requires\s+manual|action\s+required)\b",
    re.IGNORECASE,
)


def get_wud_token() -> str:
    token = os.environ.get("WUD_API_TOKEN", "")
    if not token:
        env_path = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "wud", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("WUD_API_TOKEN="):
                        return line.split("=", 1)[1].strip()
    return token


def http_get(
    url: str,
    is_json: bool = True,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
) -> Any:
    req_headers = headers if headers is not None else HEADERS
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        if is_json:
            return json.loads(content)
        return content


def clean_html(raw_html: str) -> str:
    """Strip HTML boilerplate (scripts, styles, navbars) and convert to clean markdown/text."""
    if not raw_html:
        return ""
    # Extract article or body if present
    m = re.search(r"<article[^>]*>(.*?)</article>", raw_html, re.DOTALL | re.IGNORECASE)
    if m:
        content = m.group(1)
    else:
        m_main = re.search(r"<main[^>]*>(.*?)</main>", raw_html, re.DOTALL | re.IGNORECASE)
        if m_main:
            content = m_main.group(1)
        else:
            m_body = re.search(r"<body[^>]*>(.*?)</body>", raw_html, re.DOTALL | re.IGNORECASE)
            content = m_body.group(1) if m_body else raw_html

    # Strip scripts, styles, svg, nav, header, footer
    content = re.sub(
        r"<(script|style|svg|nav|header|footer)[^>]*>.*?</\1>",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Convert headings to markdown
    content = re.sub(r"<h[1-6][^>]*>(.*?)</h[1-6]>", r"\n### \1\n", content, flags=re.DOTALL | re.IGNORECASE)
    # Convert list items
    content = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", content, flags=re.DOTALL | re.IGNORECASE)
    # Convert paragraphs and breaks
    content = re.sub(r"<br\s*/?>", r"\n", content, flags=re.IGNORECASE)
    content = re.sub(r"</?p[^>]*>", r"\n\n", content, flags=re.IGNORECASE)
    # Strip remaining HTML tags
    content = re.sub(r"<[^>]+>", " ", content)
    # Unescape HTML entities
    content = html.unescape(content)
    # Collapse excess whitespace
    content = re.sub(r"[ \t]+", " ", content)
    content = re.sub(r"\n\s*\n+", "\n\n", content)

    # Size limit guardrail: truncate if exceeding 120KB
    max_size = 120000
    if len(content) > max_size:
        content = content[:max_size] + "\n\n... [Content truncated to 120KB] ..."

    return content.strip()


def normalize_version(tag: str) -> str:
    """Strip leading 'v' and whitespace for comparative matching."""
    tag = tag.strip()
    if tag.startswith("v") and len(tag) > 1 and tag[1].isdigit():
        return tag[1:]
    return tag


def parse_linuxserver_tag(tag: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract (app_version, ls_version) from linuxserver tag."""
    # Examples:
    # 2.6.5.5623-ls162 -> ('2.6.5.5623', 'ls162')
    # 1.43.5.11029-6bf8af3f0-ls329 -> ('1.43.5.11029-6bf8af3f0', 'ls329')
    # v2.1.7-ls233 -> ('v2.1.7', 'ls233')
    # 5.1.0-r0-ls446 -> ('5.1.0-r0', 'ls446')
    m = re.match(r"^(.*?)-(ls\d+)$", tag)
    if m:
        return m.group(1), m.group(2)
    return None, None


def get_compose_file(container_data: dict) -> str:
    labels = container_data.get("labels") or {}
    path = labels.get("com.docker.compose.project.config_files")
    if path:
        return path

    container_name = container_data.get("name", "")
    if container_name:
        try:
            res = subprocess.run(
                [
                    "docker",
                    "inspect",
                    container_name,
                    "--format",
                    '{{index .Config.Labels "com.docker.compose.project.config_files"}}',
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = res.stdout.strip()
            if out:
                return out
        except Exception:
            pass
    return "Unknown"


def resolve_github_repo(container_data: dict) -> Optional[str]:
    img_name = container_data.get("image", {}).get("name", "")
    if img_name in STATIC_REPO_LOOKUP:
        kind, repo = STATIC_REPO_LOOKUP[img_name]
        if kind == "github":
            return repo

    labels = container_data.get("labels") or {}
    source = labels.get("org.opencontainers.image.source")
    if not source:
        container_name = container_data.get("name", "")
        if container_name:
            try:
                res = subprocess.run(
                    [
                        "docker",
                        "inspect",
                        container_name,
                        "--format",
                        '{{index .Config.Labels "org.opencontainers.image.source"}}',
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                source = res.stdout.strip()
            except Exception:
                pass

    if source and "github.com/" in source:
        m = re.search(r"github\.com/([^/]+/[^/#?]+)", source)
        if m:
            repo = m.group(1).rstrip(".git")
            return repo
    return None


def fetch_github_releases(owner_repo: str) -> List[dict]:
    url = f"https://api.github.com/repos/{owner_repo}/releases?per_page=30"
    return http_get(url, is_json=True)


def filter_releases_between(
    releases: List[dict], local_tag: str, remote_tag: str
) -> List[dict]:
    """
    Find releases between local_tag and remote_tag inclusive of remote_tag.
    Releases are ordered newest first.
    """
    norm_local = normalize_version(local_tag)
    norm_remote = normalize_version(remote_tag)

    is_nightly = "nightly" in remote_tag.lower()
    is_develop = "develop" in remote_tag.lower()

    selected: List[dict] = []
    found_remote = False

    for r in releases:
        tag = r.get("tag_name", "")
        tag_lower = tag.lower()

        # Skip nightly/develop releases if target tag is stable
        if not is_nightly and "nightly" in tag_lower:
            continue
        if not is_develop and "develop" in tag_lower:
            continue

        norm_r = normalize_version(tag)

        matches_remote = norm_r == norm_remote or tag == remote_tag or remote_tag in tag
        matches_local = norm_r == norm_local or tag == local_tag or local_tag in tag

        if matches_remote:
            found_remote = True

        if found_remote:
            if matches_local and tag != remote_tag:
                # Reached existing local version, stop
                break
            selected.append(r)

    # Fallback: if remote not found directly, take the newest release
    if not selected and releases:
        for r in releases:
            t = r.get("tag_name", "").lower()
            if (is_nightly or "nightly" not in t) and (is_develop or "develop" not in t):
                selected = [r]
                break
        if not selected:
            selected = [releases[0]]

    return selected


def collect_container_data(container: dict) -> dict:
    """Extract raw metadata and changelogs without regex truncation."""
    name = container.get("name", "unknown")
    img_name = container.get("image", {}).get("name", "")
    uk = container.get("updateKind", {})
    local_val = uk.get("localValue", "")
    remote_val = uk.get("remoteValue", "")
    semver_diff = uk.get("semverDiff", "unknown")
    compose_file = get_compose_file(container)

    base_data = {
        "name": name,
        "image": img_name,
        "local_version": local_val,
        "remote_version": remote_val,
        "semver_diff": semver_diff,
        "compose_file": compose_file,
        "is_linuxserver_rebuild_only": False,
        "release_urls": [],
        "raw_content": "",
        "note": None,
    }

    # 1. LinuxServer images check
    is_linuxserver = (
        "linuxserver/" in img_name
        or "lscr.io/linuxserver/" in img_name
        or any(k in img_name for k in LINUXSERVER_UPSTREAM.keys())
    )

    if is_linuxserver:
        local_app, local_ls = parse_linuxserver_tag(local_val)
        remote_app, remote_ls = parse_linuxserver_tag(remote_val)

        # Check if ONLY the ls### bumped
        if local_app and remote_app and local_app == remote_app and local_ls != remote_ls:
            base_data["is_linuxserver_rebuild_only"] = True
            base_data["note"] = (
                f"linuxserver base image / security update only "
                f"({local_ls} → {remote_ls} bump). No upstream app changes."
            )
            return base_data

        # If app version changed on LinuxServer:
        app_key = None
        for k in LINUXSERVER_UPSTREAM.keys():
            if k in img_name or k == name:
                app_key = k
                break

        if app_key:
            upstream_repo, docker_repo = LINUXSERVER_UPSTREAM[app_key]
            release_urls: List[str] = []
            raw_parts: List[str] = []

            # Fetch upstream releases if available
            if upstream_repo:
                try:
                    up_rels = fetch_github_releases(upstream_repo)
                    up_filtered = filter_releases_between(
                        up_rels, local_app or local_val, remote_app or remote_val
                    )
                    for r in up_filtered:
                        url = r.get("html_url")
                        if url and url not in release_urls:
                            release_urls.append(url)
                        tag = r.get("tag_name", "")
                        r_name = r.get("name") or tag
                        body = r.get("body") or ""
                        raw_parts.append(f"## [{upstream_repo}] Release {tag} ({r_name})\n\n{body.strip()}")
                except Exception as e:
                    raw_parts.append(f"Notice: Failed to fetch upstream releases from {upstream_repo}: {e}")

            # Fetch linuxserver docker releases
            try:
                ls_rels = fetch_github_releases(docker_repo)
                ls_filtered = filter_releases_between(ls_rels, local_val, remote_val)
                for r in ls_filtered:
                    url = r.get("html_url")
                    if url and url not in release_urls:
                        release_urls.append(url)
                    tag = r.get("tag_name", "")
                    r_name = r.get("name") or tag
                    body = r.get("body") or ""
                    raw_parts.append(f"## [{docker_repo}] Release {tag} ({r_name})\n\n{body.strip()}")
            except Exception:
                pass

            base_data["release_urls"] = release_urls or [f"https://github.com/{docker_repo}/releases"]
            base_data["raw_content"] = "\n\n---\n\n".join(raw_parts)
            return base_data

    # 2. Vikunja
    if "vikunja" in img_name:
        try:
            releases = fetch_github_releases("go-vikunja/vikunja")
            filtered = filter_releases_between(releases, local_val, remote_val)
            release_urls = [r["html_url"] for r in filtered if r.get("html_url")]
            raw_parts = []
            for r in filtered:
                tag = r.get("tag_name", "")
                r_name = r.get("name") or tag
                body = r.get("body") or ""
                raw_parts.append(f"## Release {tag} ({r_name})\n\n{body.strip()}")
            if raw_parts:
                base_data["release_urls"] = release_urls
                base_data["raw_content"] = "\n\n---\n\n".join(raw_parts)
                return base_data
        except Exception:
            pass

        # Fallback to kolaente.dev HTML if needed
        try:
            url = "https://kolaente.dev/vikunja/vikunja/releases"
            raw_html = http_get(url, is_json=False, timeout=10)
            base_data["release_urls"] = [url]
            base_data["raw_content"] = clean_html(raw_html)
            return base_data
        except Exception as e:
            base_data["release_urls"] = ["https://kolaente.dev/vikunja/vikunja/releases"]
            base_data["note"] = f"Notice: Vikunja changelog fetch error: {e}"
            return base_data

    # 3. Home Assistant
    if "home-assistant" in img_name or name == "homeassistant":
        try:
            releases = fetch_github_releases("home-assistant/core")
            filtered = filter_releases_between(releases, local_val, remote_val)
            release_urls = []
            raw_parts = []

            blog_urls_fetched = set()
            for r in filtered:
                url = r.get("html_url")
                if url and url not in release_urls:
                    release_urls.append(url)
                body = r.get("body") or ""

                # Look for blog post links in release body
                b_matches = re.findall(
                    r"https://www\.home-assistant\.io/blog/\d{4}/\d{2}/\d{2}/release-\d+/?",
                    body,
                )
                for b_url in b_matches:
                    b_url = b_url.rstrip("/") + "/"
                    if b_url not in blog_urls_fetched:
                        blog_urls_fetched.add(b_url)
                        release_urls.insert(0, b_url)
                        try:
                            blog_html = http_get(b_url, is_json=False, timeout=12)
                            cleaned_blog = clean_html(blog_html)
                            raw_parts.append(f"# Home Assistant Blog Announcement ({b_url})\n\n{cleaned_blog}")
                        except Exception as e:
                            raw_parts.append(f"Notice: Failed to fetch blog post {b_url}: {e}")

                tag = r.get("tag_name", "")
                r_name = r.get("name") or tag
                raw_parts.append(f"## Release {tag} ({r_name})\n\n{body.strip()}")

            base_data["release_urls"] = release_urls or ["https://github.com/home-assistant/core/releases"]
            base_data["raw_content"] = "\n\n---\n\n".join(raw_parts)
            return base_data
        except Exception as e:
            base_data["release_urls"] = ["https://github.com/home-assistant/core/releases"]
            base_data["note"] = f"Notice: Home Assistant changelog fetch error: {e}"
            return base_data

    # 4. Standard GitHub Images
    gh_repo = resolve_github_repo(container)
    if gh_repo:
        try:
            releases = fetch_github_releases(gh_repo)
            filtered = filter_releases_between(releases, local_val, remote_val)
            release_urls = [r["html_url"] for r in filtered if r.get("html_url")]
            raw_parts = []
            for r in filtered:
                tag = r.get("tag_name", "")
                r_name = r.get("name") or tag
                body = r.get("body") or ""
                raw_parts.append(f"## Release {tag} ({r_name})\n\n{body.strip()}")

            base_data["release_urls"] = release_urls or [f"https://github.com/{gh_repo}/releases"]
            base_data["raw_content"] = "\n\n---\n\n".join(raw_parts)
            return base_data
        except Exception as e:
            base_data["release_urls"] = [f"https://github.com/{gh_repo}/releases"]
            base_data["note"] = f"Notice: Could not fetch changelog details from {gh_repo}: {e}"
            return base_data

    # Fallback if no repo was resolved
    base_data["note"] = "Upstream release notes URL could not be resolved automatically."
    return base_data


def format_container_markdown(data: dict) -> str:
    """Format container data as markdown (fallback for non-JSON mode)."""
    name = data["name"]
    local_val = data["local_version"]
    remote_val = data["remote_version"]
    semver_diff = data["semver_diff"]
    compose_file = data["compose_file"]
    note = data.get("note")
    release_urls = data.get("release_urls") or []
    raw_content = data.get("raw_content") or ""

    lines = [
        f"## [{name}]  {local_val} → {remote_val}  ({semver_diff})",
        f"Compose file: `{compose_file}`",
        "",
    ]

    if note:
        lines.append(f"*{note}*")
        lines.append("")
        if data.get("is_linuxserver_rebuild_only"):
            return "\n".join(lines)

    lines.append("### Releases covered")
    if release_urls:
        for url in release_urls:
            # Derive a label from url if possible
            tag_match = re.search(r"tag/([^/?#]+)", url)
            tag_label = tag_match.group(1) if tag_match else url
            lines.append(f"- [{tag_label}]({url})")
    else:
        lines.append(f"- Version bump {local_val} → {remote_val}")
    lines.append("")

    # Extract summary bullets from raw content
    summary_bullets = []
    breaking_bullets = []
    for line in raw_content.splitlines():
        line_str = line.strip()
        if not line_str or line_str.startswith("#"):
            continue
        if line_str.startswith(("- ", "* ")):
            bullet = re.sub(r"^[-*]\s+", "", line_str).strip()
            if not bullet or len(bullet) < 5:
                continue
            if BREAKING_PATTERNS.search(bullet):
                if bullet not in breaking_bullets:
                    breaking_bullets.append(bullet)
            elif bullet not in summary_bullets and len(summary_bullets) < 6:
                summary_bullets.append(bullet)

    lines.append("### Summary")
    if summary_bullets:
        for b in summary_bullets[:6]:
            lines.append(f"- {b}")
    else:
        lines.append("- Upstream release with maintenance and performance improvements.")
    lines.append("")

    if breaking_bullets or semver_diff == "major":
        lines.append("⚠️ BREAKING CHANGES")
        if breaking_bullets:
            for b in breaking_bullets[:8]:
                lines.append(f"- {b}")
        else:
            lines.append(f"- Major version change ({semver_diff}). Review release notes for breaking changes.")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Check WUD for container updates")
    parser.add_argument(
        "--json",
        "--raw",
        action="store_true",
        dest="json_mode",
        help="Output structured JSON array containing raw changelogs",
    )
    args = parser.parse_args()

    try:
        wud_token = get_wud_token()
        wud_headers = {"User-Agent": "homelab-check-updates/1.0"}
        if wud_token:
            wud_headers["Authorization"] = f"Bearer {wud_token}"
        raw_containers = http_get(WUD_URL, is_json=True, timeout=15, headers=wud_headers)
    except Exception as e:
        print(f"Error querying WUD at {WUD_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    updates = [c for c in raw_containers if c.get("updateAvailable") is True]

    if not updates:
        if args.json_mode:
            print("[]")
        else:
            print("No updates available.")
        sys.exit(0)

    containers_data = [collect_container_data(c) for c in updates]

    if args.json_mode:
        print(json.dumps(containers_data, indent=2))
    else:
        sections = [format_container_markdown(d) for d in containers_data]
        print("\n---\n\n".join(sections))


if __name__ == "__main__":
    main()
