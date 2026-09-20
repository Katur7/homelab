#!/bin/bash
set -euo pipefail

# Check 1: Container running state
if [ "$(docker inspect -f '{{.State.Running}}' wireguard 2>/dev/null)" != "true" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] WireGuard container is not running" >&2
  exit 1
fi

# Check 2: Active wg0 interface inside container
if ! docker exec wireguard wg show wg0 >/dev/null 2>&1; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wg0 interface is not active inside container" >&2
  exit 1
fi

# Load push URL secret from host file, local .env, or environment variable
PUSH_URL_FILE="/root/.uptime-kuma-push-wireguard"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL=""

if [[ -f "$PUSH_URL_FILE" ]]; then
  PUSH_URL="$(cat "$PUSH_URL_FILE")"
elif [[ -f "$SCRIPT_DIR/../.env" ]] && grep -q '^UPTIME_KUMA_WIREGUARD_PUSH_URL=' "$SCRIPT_DIR/../.env"; then
  PUSH_URL="$(grep '^UPTIME_KUMA_WIREGUARD_PUSH_URL=' "$SCRIPT_DIR/../.env" | cut -d '=' -f2- | tr -d '\"'\' )"
elif [[ -n "${UPTIME_KUMA_WIREGUARD_PUSH_URL:-}" ]]; then
  PUSH_URL="$UPTIME_KUMA_WIREGUARD_PUSH_URL"
fi

if [[ -n "$PUSH_URL" ]]; then
  curl -fsS -m 5 --retry 2 "$PUSH_URL" > /dev/null
fi

