#!/usr/bin/env python3
"""
Auto-updater for WUD HTTP trigger.
Receives WUD webhook POSTs, applies container updates, commits on success.
Safe list: containers must have label wud.autoupdate=true to be eligible.
"""

import datetime
import json
import logging
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

HA_WEBHOOK_URL = os.environ.get("HA_WEBHOOK_URL", "")
REPO_PATH = os.environ.get("REPO_PATH", "/home/grimur/homelab")
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "wud-autoupdater")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "wud-autoupdater@pippinn.me")


def parse_major(tag: str) -> int | None:
    """Strip leading v, split on '.', return first element as major version int."""
    try:
        return int(tag.lstrip("v").split(".")[0])
    except (ValueError, IndexError):
        return None


def container_inspect(container_name: str) -> tuple[str, str, bool]:
    """
    Return (compose_file_path_in_container, service_name, autoupdate_enabled)
    from a single docker inspect call.
    """
    fmt = (
        '{{index .Config.Labels "com.docker.compose.project.config_files"}}'
        " "
        '{{index .Config.Labels "com.docker.compose.service"}}'
        " "
        '{{index .Config.Labels "wud.autoupdate"}}'
    )
    result = subprocess.run(
        ["docker", "inspect", container_name, "--format", fmt],
        capture_output=True,
        text=True,
    )
    parts = result.stdout.strip().split()
    if len(parts) >= 2:
        container_path = parts[0]
        service = parts[1]
        autoupdate = parts[2].lower() == "true" if len(parts) >= 3 else False
        return container_path, service, autoupdate
    return "", "", False


def container_image_id(container_name: str) -> str:
    result = subprocess.run(
        ["docker", "inspect", container_name, "--format", "{{.Image}}"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def container_full_image(container_name: str) -> str:
    """Return fully-qualified image reference (registry/name:tag) from running container."""
    result = subprocess.run(
        ["docker", "inspect", container_name, "--format", "{{.Config.Image}}"],
        capture_output=True,
        text=True,
    )
    ref = result.stdout.strip()
    # Strip existing tag — caller will append new_tag
    return ref.rsplit(":", 1)[0] if ":" in ref else ref


def update_compose_tag(compose_path: str, old_tag: str, new_tag: str) -> bool:
    """Replace old_tag with new_tag in compose file. Returns True if changed."""
    with open(compose_path) as f:
        content = f.read()
    new_content = content.replace(old_tag, new_tag, 1)
    if new_content == content:
        return False
    with open(compose_path, "w") as f:
        f.write(new_content)
    return True


def revert_compose_tag(compose_path: str, new_tag: str, old_tag: str) -> None:
    with open(compose_path) as f:
        content = f.read()
    with open(compose_path, "w") as f:
        f.write(content.replace(new_tag, old_tag, 1))
    log.info("Reverted %s in %s back to %s", new_tag, compose_path, old_tag)


def wait_for_healthy(container_name: str, timeout: int = 30) -> bool:
    """
    Poll container until confirmed healthy or timeout.
    - Has HEALTHCHECK: wait for 'healthy' status
    - No HEALTHCHECK: wait for 'running', then confirm it stays up for 5s
    """
    log.info("Health check: waiting up to %ds for %s", timeout, container_name)
    deadline = time.monotonic() + timeout
    running_since: float | None = None

    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker", "inspect", container_name,
                "--format",
                "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
            ],
            capture_output=True,
            text=True,
        )
        parts = result.stdout.strip().split()
        status = parts[0] if parts else ""
        health = parts[1] if len(parts) > 1 else ""
        elapsed = int(timeout - (deadline - time.monotonic()))
        log.info("Health check [%ds]: status=%s health=%s", elapsed, status, health or "none")

        if health == "healthy":
            return True
        if status in ("exited", "dead") or health == "unhealthy":
            running_since = None
            return False
        if status == "running" and not health:
            # No HEALTHCHECK — confirm stable for 5s before passing
            if running_since is None:
                running_since = time.monotonic()
                log.info("Container running (no healthcheck) — confirming stability for 5s")
            elif time.monotonic() - running_since >= 5:
                return True
        else:
            running_since = None

        time.sleep(2)
    log.warning("Health check timed out after %ds", timeout)
    return False


def _send_notification(payload: bytes) -> None:
    try:
        req = Request(HA_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"})
        urlopen(req, timeout=5)
        log.info("Failure notification sent to HA")
    except Exception as exc:
        log.error("Failed to notify HA: %s", exc)


def notify_failure(service: str, old_tag: str, new_tag: str, reason: str) -> None:
    if not HA_WEBHOOK_URL:
        log.warning("HA_WEBHOOK_URL not set — skipping failure notification")
        return
    payload = json.dumps(
        {"service": service, "old_tag": old_tag, "new_tag": new_tag, "reason": reason}
    ).encode()
    hour = time.localtime().tm_hour
    if hour >= 22 or hour < 9:
        now = datetime.datetime.now()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        delay = (target - now).total_seconds()
        log.info("Quiet hours — notification deferred by %ds (until 09:00)", int(delay))
        t = threading.Timer(delay, _send_notification, args=[payload])
        t.daemon = True
        t.start()
    else:
        _send_notification(payload)


def git_commit(compose_path: str, service: str, old_tag: str, new_tag: str) -> None:
    rel_path = os.path.relpath(compose_path, REPO_PATH)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": GIT_USER_NAME,
        "GIT_AUTHOR_EMAIL": GIT_USER_EMAIL,
        "GIT_COMMITTER_NAME": GIT_USER_NAME,
        "GIT_COMMITTER_EMAIL": GIT_USER_EMAIL,
    }
    log.info("Committing %s", rel_path)
    subprocess.run(["git", "-C", REPO_PATH, "add", rel_path], check=True, env=env)
    subprocess.run(
        ["git", "-C", REPO_PATH, "commit", "-m", f"Auto-update {service}: {old_tag} \u2192 {new_tag}"],
        check=True,
        env=env,
    )


def handle_update(payload: dict) -> None:
    container_name = payload.get("name", "")
    image_name = payload.get("image", {}).get("name", "")
    old_tag = payload.get("image", {}).get("tag", {}).get("value", "")
    new_tag = payload.get("result", {}).get("tag", "")

    log.info("--- Update received: %s  %s → %s ---", container_name, old_tag, new_tag)

    if not all([container_name, image_name, old_tag, new_tag]):
        log.warning("Incomplete payload, skipping: %s", payload)
        return

    # Safe list: check wud.autoupdate=true label via docker inspect
    compose_path, service, autoupdate = container_inspect(container_name)
    if not autoupdate:
        log.info("Skipping %s — wud.autoupdate label not set", container_name)
        return

    if not compose_path:
        log.error("Could not resolve compose path for %s", container_name)
        notify_failure(container_name, old_tag, new_tag, "Could not resolve compose path")
        return

    log.info("Compose file: %s  service: %s", compose_path, service)

    # Major version gate
    old_major, new_major = parse_major(old_tag), parse_major(new_tag)
    log.info("Major version check: %s (major=%s) → %s (major=%s)", old_tag, old_major, new_tag, new_major)
    if old_major is not None and new_major is not None and new_major > old_major:
        log.info("Skipping — major version bump blocked")
        return

    # Record old image digest for rollback
    old_image_id = container_image_id(container_name)
    log.info("Current image digest: %s", old_image_id)

    # Get fully-qualified image name from running container (WUD payload strips registry)
    image_ref = container_full_image(container_name)
    log.info("Pulling %s:%s", image_ref, new_tag)
    pull = subprocess.run(
        ["docker", "pull", f"{image_ref}:{new_tag}"], capture_output=True, text=True
    )
    if pull.returncode != 0:
        log.error("Pull failed: %s", pull.stderr.strip())
        notify_failure(service, old_tag, new_tag, f"Pull failed: {pull.stderr.strip()}")
        return
    log.info("Pull complete")

    # Edit compose.yaml
    log.info("Updating compose tag: %s → %s in %s", old_tag, new_tag, compose_path)
    if not update_compose_tag(compose_path, old_tag, new_tag):
        log.error("Tag %s not found in %s — aborting", old_tag, compose_path)
        notify_failure(service, old_tag, new_tag, "Tag not found in compose file")
        return

    # Bring up container with new image
    log.info("Starting %s via docker compose", service)
    up = subprocess.run(
        ["docker", "compose", "-f", compose_path, "up", "-d", service],
        capture_output=True,
        text=True,
    )
    if up.returncode != 0:
        log.error("docker compose up failed: %s", up.stderr.strip())
        revert_compose_tag(compose_path, new_tag, old_tag)
        subprocess.run(["docker", "compose", "-f", compose_path, "up", "-d", "--no-pull", service])
        notify_failure(service, old_tag, new_tag, "docker compose up failed")
        return
    log.info("Container started")

    # Health check
    if not wait_for_healthy(container_name):
        log.error("Health check failed — rolling back %s to %s", service, old_tag)
        revert_compose_tag(compose_path, new_tag, old_tag)
        subprocess.run(["docker", "tag", old_image_id, f"{image_ref}:{old_tag}"])
        subprocess.run(["docker", "compose", "-f", compose_path, "up", "-d", "--no-pull", service])
        notify_failure(service, old_tag, new_tag, f"Health check failed — rolled back {new_tag} → {old_tag}")
        return

    log.info("Health check passed")

    # Commit
    try:
        git_commit(compose_path, service, old_tag, new_tag)
        log.info("--- Done: %s updated %s → %s (compose updated, committed) ---", service, old_tag, new_tag)
    except Exception as exc:
        log.error("Git commit failed (update was applied): %s", exc)


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()
        try:
            handle_update(json.loads(body))
        except Exception as exc:
            log.exception("Unhandled error: %s", exc)

    def log_message(self, fmt, *args):
        log.info(fmt, *args)


def main():
    subprocess.run(["git", "config", "--global", "safe.directory", REPO_PATH])
    port = int(os.environ.get("PORT", 8080))
    log.info("Starting auto-updater on port %d", port)
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
