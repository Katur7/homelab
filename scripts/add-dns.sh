#!/usr/bin/env bash
# add-dns.sh — Add A + AAAA record for <service>.pippinn.me to PiHole via v6 API
# Usage: ./scripts/add-dns.sh <service-name>
#
# API: PUT /api/config/dns/hosts/<url-encoded "ip domain">

set -euo pipefail

PIHOLE_HOST="http://192.168.86.27"
IPV4="192.168.86.17"
IPV6="2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362"
DOMAIN_SUFFIX="pippinn.me"
ENV_FILE="$(dirname "$0")/../infrastructure/dns/.env"

# --- Validate input ---
if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <service-name>" >&2
  exit 1
fi

SERVICE="$1"
FQDN="${SERVICE}.${DOMAIN_SUFFIX}"

# --- Resolve password ---
if [[ -z "${PIHOLE_PASSWORD:-}" ]]; then
  if [[ -f "$ENV_FILE" ]]; then
    PIHOLE_PASSWORD=$(grep -m1 '^FTLCONF_webserver_api_password=' "$ENV_FILE" | cut -d= -f2-)
  fi
fi

if [[ -z "${PIHOLE_PASSWORD:-}" ]]; then
  echo "Error: no password found. Set \$PIHOLE_PASSWORD or ensure infrastructure/dns/.env exists." >&2
  exit 1
fi

# --- Authenticate ---
echo "Authenticating with PiHole at ${PIHOLE_HOST}..."
AUTH_RESPONSE=$(curl -sf -X POST "${PIHOLE_HOST}/api/auth" \
  -H "Content-Type: application/json" \
  -d "{\"password\": \"${PIHOLE_PASSWORD}\"}")

SID=$(echo "$AUTH_RESPONSE" | jq -r '.session.sid // empty')

if [[ -z "$SID" ]]; then
  echo "Error: authentication failed. Check password." >&2
  exit 1
fi

echo "Authenticated (SID: ${SID:0:8}...)"

# --- Logout on exit ---
cleanup() {
  curl -sf -X DELETE "${PIHOLE_HOST}/api/auth" \
    -H "X-FTL-SID: ${SID}" > /dev/null 2>&1 || true
}
trap cleanup EXIT

# --- URL-encode "ip domain" for path segment ---
urlencode() {
  jq -rn --arg s "$1" '$s | @uri'
}

# --- Add a single DNS record via PUT ---
add_record() {
  local ip="$1"
  local type="$2"
  local entry="${ip} ${FQDN}"
  local encoded
  encoded=$(urlencode "$entry")

  local response http_status body
  response=$(curl -s -w "\n%{http_code}" -X PUT \
    "${PIHOLE_HOST}/api/config/dns/hosts/${encoded}" \
    -H "X-FTL-SID: ${SID}")

  http_status=$(echo "$response" | tail -1)
  body=$(echo "$response" | head -n -1)

  if [[ "$http_status" == "200" || "$http_status" == "201" || "$http_status" == "204" ]]; then
    echo "  [OK] ${type} record: ${FQDN} → ${ip}"
  else
    echo "  [FAIL] ${type} record (HTTP ${http_status}): ${FQDN} → ${ip}" >&2
    [[ -n "$body" ]] && echo "  Response: ${body}" >&2
    return 1
  fi
}

# --- Add records ---
echo "Adding DNS records for ${FQDN}..."
add_record "$IPV4" "A"
add_record "$IPV6" "AAAA"
echo "Done."
