#!/bin/bash
set -euo pipefail

# Optional job identifier (e.g. "homelab", "photos")
JOB="${1:-homelab}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PUSH_URL=""

# Check job-specific host secret file first, then generic fallback, then .env
if [[ -f "/root/.uptime-kuma-push-local-${JOB}" ]]; then
  PUSH_URL="$(cat "/root/.uptime-kuma-push-local-${JOB}")"
elif [[ -f "/root/.uptime-kuma-push-local" ]]; then
  PUSH_URL="$(cat "/root/.uptime-kuma-push-local")"
elif [[ -f "$SCRIPT_DIR/.env" ]]; then
  VAR_NAME="UPTIME_KUMA_LOCAL_$(echo "$JOB" | tr '[:lower:]' '[:upper:]')_PUSH_URL"
  if grep -q "^${VAR_NAME}=" "$SCRIPT_DIR/.env"; then
    PUSH_URL="$(grep "^${VAR_NAME}=" "$SCRIPT_DIR/.env" | cut -d '=' -f2- | tr -d '\"'\' )"
  fi
fi

if [[ -n "$PUSH_URL" ]]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Sending heartbeat to Uptime Kuma for local backup (${JOB})"
  curl -fsS -m 10 --retry 3 "$PUSH_URL" > /dev/null
else
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] Warning: No push URL configured for local backup (${JOB})" >&2
fi
