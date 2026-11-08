#!/usr/bin/env python3
"""
CLI script to query WUD for pending container updates, resolve source repositories,
fetch release notes between local and remote versions, detect breaking changes,
and output a structured Markdown report.
"""

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
    "vikunja/vikunja": ("vikunja", "https://kolaente.dev/vikunja/vikunja/releases"),
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


def http_get(url: str, is_json: bool = True, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        content = resp.read().decode("utf-8", errors="ignore")
        if is_json:
            return json.loads(content)
        return content


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

        # Skip nightly/develop releases if the target tag is a stable release
        if not is_nightly and "nightly" in tag_lower:
            continue
        if not is_develop and "develop" in tag_lower:
            continue

        norm_r = normalize_version(tag)

        # Some repos use tag prefixes like 'release-2.0'
        matches_remote = norm_r == norm_remote or tag == remote_tag or remote_tag in tag
        matches_local = norm_r == norm_local or tag == local_tag or local_tag in tag

        if matches_remote:
            found_remote = True

        if found_remote:
            if matches_local and tag != remote_tag:
                # Reached existing local version, stop
                break
            selected.append(r)

    # Fallback: if remote not found directly (e.g. slight tag variation), take the first release
    if not selected and releases:
        # Pick the first non-nightly/non-develop release if possible
        for r in releases:
            t = r.get("tag_name", "").lower()
            if (is_nightly or "nightly" not in t) and (is_develop or "develop" not in t):
                selected = [r]
                break
        if not selected:
            selected = [releases[0]]

    return selected


def extract_summary_and_breaking(
    releases: List[dict], semver_diff: str
) -> Tuple[List[str], List[str], List[dict]]:
    """
    Parse release bodies to extract:
    - releases_covered info (tag, url, title, has_breaking)
    - summary bullets
    - breaking changes bullets
    """
    releases_covered = []
    summary_bullets = []
    breaking_bullets = []

    for r in releases:
        tag = r.get("tag_name", "")
        name = r.get("name") or tag
        url = r.get("html_url", "")
        body = r.get("body") or ""

        # Check for breaking changes in this release
        has_breaking = bool(BREAKING_PATTERNS.search(body)) or (semver_diff == "major")

        # Extract explicit breaking change sections from markdown
        # Headers like: ### ⚠️ Breaking Changes, ## Breaking changes, etc.
        breaking_sec = re.findall(
            r"(?:^|\n)#{1,4}\s*[^\n]*(?:breaking|migration|deprecat)[^\n]*\n(.*?)(?=\n#{1,4}\s|\Z)",
            body,
            re.IGNORECASE | re.DOTALL,
        )
        for sec in breaking_sec:
            for line in sec.strip().splitlines():
                line_str = line.strip()
                if line_str.startswith(("- ", "* ")):
                    bullet = re.sub(r"^[-*]\s+", "", line_str).strip()
                    if bullet and bullet not in breaking_bullets:
                        breaking_bullets.append(f"[{tag}] {bullet}")

        # If no explicit section but pattern matched in text, grab matching lines
        if has_breaking and not breaking_sec:
            for line in body.splitlines():
                line_str = line.strip()
                if BREAKING_PATTERNS.search(line_str) and line_str.startswith(("- ", "* ")):
                    bullet = re.sub(r"^[-*]\s+", "", line_str).strip()
                    if bullet and bullet not in breaking_bullets:
                        breaking_bullets.append(f"[{tag}] {bullet}")

        # Extract summary bullets
        bullet_count = 0
        for line in body.splitlines():
            line_str = line.strip()
            # Skip empty lines, headers, full changelog link, contributor notes
            if not line_str or line_str.startswith("#"):
                continue
            if re.search(r"(full changelog|contributors|@dependabot)", line_str, re.IGNORECASE):
                continue
            if line_str.startswith(("- ", "* ")):
                bullet = re.sub(r"^[-*]\s+", "", line_str).strip()
                if bullet and bullet not in summary_bullets and bullet not in breaking_bullets:
                    summary_bullets.append(f"[{tag}] {bullet}")
                    bullet_count += 1
                    if bullet_count >= 3:
                        break

        # Fallback if no bullets were formatted in markdown
        if bullet_count == 0:
            first_line = ""
            for l in body.splitlines():
                if l.strip() and not l.strip().startswith("#"):
                    first_line = l.strip()
                    break
            if first_line:
                summary_bullets.append(f"[{tag}] {first_line[:120]}")

        releases_covered.append(
            {
                "tag": tag,
                "name": name,
                "url": url,
                "has_breaking": has_breaking,
            }
        )

    return summary_bullets, breaking_bullets, releases_covered


def process_home_assistant(
    container: dict, local_val: str, remote_val: str, semver_diff: str
) -> Tuple[List[str], List[str], List[dict]]:
    """Special handling for Home Assistant blog posts and core releases."""
    releases = fetch_github_releases("home-assistant/core")
    rel_filtered = filter_releases_between(releases, local_val, remote_val)

    summary_bullets, breaking_bullets, covered = extract_summary_and_breaking(
        rel_filtered, semver_diff
    )

    # For monthly releases, check blog post for backward-incompatible changes
    for r in rel_filtered:
        body = r.get("body", "")
        m = re.search(r"https://www\.home-assistant\.io/blog/\d{4}/\d{2}/\d{2}/release-\d+/", body)
        if m:
            blog_url = m.group(0)
            try:
                blog_html = http_get(blog_url, is_json=False, timeout=10)
                # Find backward-incompatible section
                bm = re.search(
                    r"name=[\x27\x22](?:backward-incompatible-changes|breaking-changes)[\x27\x22].*?</h2>\s*(.*?)(?=<h2|\Z)",
                    blog_html,
                    re.IGNORECASE | re.DOTALL,
                )
                if bm:
                    sec_text = bm.group(1)
                    # Extract list items or headings
                    items = re.findall(r"<li>(.*?)</li>", sec_text, re.DOTALL)
                    for item in items[:8]:
                        clean = re.sub(r"<[^>]+>", " ", item).strip()
                        clean = html.unescape(clean)
                        clean = re.sub(r"\s+", " ", clean)
                        if clean and len(clean) > 10:
                            breaking_bullets.append(f"[HA Blog] {clean}")
            except Exception:
                pass

    return summary_bullets, breaking_bullets, covered


def process_vikunja(
    local_val: str, remote_val: str
) -> Tuple[List[str], List[str], List[dict]]:
    """Fetch Vikunja release notes from Kolaente Gitea HTML."""
    url = "https://kolaente.dev/vikunja/vikunja/releases"
    html_content = http_get(url, is_json=False, timeout=10)

    covered = [
        {
            "tag": remote_val,
            "name": f"Vikunja {remote_val}",
            "url": url,
            "has_breaking": False,
        }
    ]
    summary = [f"Vikunja update from {local_val} to {remote_val} (see {url})"]
    breaking: List[str] = []

    # Simple scan for breaking keywords in release page
    if BREAKING_PATTERNS.search(html_content):
        breaking.append(f"Potential breaking change or migration noted on {url}")

    return summary, breaking, covered


def format_container_markdown(
    name: str,
    local_val: str,
    remote_val: str,
    semver_diff: str,
    compose_file: str,
    releases_covered: List[dict],
    summary_bullets: List[str],
    breaking_bullets: List[str],
    note: Optional[str] = None,
) -> str:
    lines = [
        f"## [{name}]  {local_val} → {remote_val}  ({semver_diff})",
        f"Compose file: `{compose_file}`",
        "",
    ]

    if note:
        lines.append(f"*{note}*")
        lines.append("")
        return "\n".join(lines)

    lines.append("### Releases covered")
    if releases_covered:
        for r in releases_covered:
            tag = r["tag"]
            url = r["url"]
            name_text = r["name"]
            breaking_flag = "  ⚠️ BREAKING" if r["has_breaking"] else ""
            lines.append(f"- [{tag}]({url}) — {name_text}{breaking_flag}")
    else:
        lines.append(f"- Version bump {local_val} → {remote_val}")
    lines.append("")

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


def process_container(container: dict) -> str:
    name = container.get("name", "unknown")
    img_name = container.get("image", {}).get("name", "")
    uk = container.get("updateKind", {})
    local_val = uk.get("localValue", "")
    remote_val = uk.get("remoteValue", "")
    semver_diff = uk.get("semverDiff", "unknown")
    compose_file = get_compose_file(container)

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
            note = (
                f"linuxserver base image / security update only "
                f"({local_ls} → {remote_ls} bump). No upstream app changes."
            )
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=[],
                summary_bullets=[],
                breaking_bullets=[],
                note=note,
            )

        # If app version changed on LinuxServer:
        app_key = None
        for k in LINUXSERVER_UPSTREAM.keys():
            if k in img_name or k == name:
                app_key = k
                break

        if app_key:
            upstream_repo, docker_repo = LINUXSERVER_UPSTREAM[app_key]
            try:
                # Fetch upstream releases if available
                if upstream_repo:
                    up_rels = fetch_github_releases(upstream_repo)
                    up_filtered = filter_releases_between(
                        up_rels, local_app or local_val, remote_app or remote_val
                    )
                    summary, breaking, covered = extract_summary_and_breaking(
                        up_filtered, semver_diff
                    )
                else:
                    summary, breaking, covered = [], [], []

                # Also include linuxserver release link
                ls_rels = fetch_github_releases(docker_repo)
                ls_filtered = filter_releases_between(ls_rels, local_val, remote_val)
                _, ls_breaking, ls_covered = extract_summary_and_breaking(
                    ls_filtered, semver_diff
                )

                breaking.extend(ls_breaking)
                covered.extend(ls_covered)

                return format_container_markdown(
                    name=name,
                    local_val=local_val,
                    remote_val=remote_val,
                    semver_diff=semver_diff,
                    compose_file=compose_file,
                    releases_covered=covered,
                    summary_bullets=summary,
                    breaking_bullets=breaking,
                )
            except Exception as e:
                return format_container_markdown(
                    name=name,
                    local_val=local_val,
                    remote_val=remote_val,
                    semver_diff=semver_diff,
                    compose_file=compose_file,
                    releases_covered=[],
                    summary_bullets=[f"Upstream release notes: https://github.com/{upstream_repo or docker_repo}/releases"],
                    breaking_bullets=[],
                    note=f"Notice: Could not fetch changelog details: {e}",
                )

    # 2. Vikunja
    if "vikunja" in img_name:
        try:
            summary, breaking, covered = process_vikunja(local_val, remote_val)
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=covered,
                summary_bullets=summary,
                breaking_bullets=breaking,
            )
        except Exception as e:
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=[],
                summary_bullets=[],
                breaking_bullets=[],
                note=f"Notice: Vikunja changelog fetch error: {e}",
            )

    # 3. Home Assistant
    if "home-assistant" in img_name or name == "homeassistant":
        try:
            summary, breaking, covered = process_home_assistant(
                container, local_val, remote_val, semver_diff
            )
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=covered,
                summary_bullets=summary,
                breaking_bullets=breaking,
            )
        except Exception as e:
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=[],
                summary_bullets=[],
                breaking_bullets=[],
                note=f"Notice: Home Assistant changelog fetch error: {e}",
            )

    # 4. Standard GitHub Images
    gh_repo = resolve_github_repo(container)
    if gh_repo:
        try:
            releases = fetch_github_releases(gh_repo)
            filtered = filter_releases_between(releases, local_val, remote_val)
            summary, breaking, covered = extract_summary_and_breaking(
                filtered, semver_diff
            )
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=covered,
                summary_bullets=summary,
                breaking_bullets=breaking,
            )
        except Exception as e:
            return format_container_markdown(
                name=name,
                local_val=local_val,
                remote_val=remote_val,
                semver_diff=semver_diff,
                compose_file=compose_file,
                releases_covered=[
                    {
                        "tag": remote_val,
                        "name": f"Release {remote_val}",
                        "url": f"https://github.com/{gh_repo}/releases",
                        "has_breaking": semver_diff == "major",
                    }
                ],
                summary_bullets=[],
                breaking_bullets=[],
                note=f"Notice: Could not fetch changelog details from {gh_repo}: {e}",
            )

    # Fallback if no repo was resolved
    return format_container_markdown(
        name=name,
        local_val=local_val,
        remote_val=remote_val,
        semver_diff=semver_diff,
        compose_file=compose_file,
        releases_covered=[],
        summary_bullets=[],
        breaking_bullets=[],
        note="Upstream release notes URL could not be resolved automatically.",
    )


def main():
    try:
        raw_containers = http_get(WUD_URL, is_json=True, timeout=15)
    except Exception as e:
        print(f"Error querying WUD at {WUD_URL}: {e}", file=sys.stderr)
        sys.exit(1)

    updates = [c for c in raw_containers if c.get("updateAvailable") is True]

    if not updates:
        print("No updates available.")
        sys.exit(0)

    sections = []
    for c in updates:
        md = process_container(c)
        sections.append(md)

    print("\n---\n\n".join(sections))


if __name__ == "__main__":
    main()
