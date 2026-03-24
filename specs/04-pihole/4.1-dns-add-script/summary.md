# Summary: 4.1 PiHole DNS Add Script

## What was changed
- **New file:** `scripts/add-dns.sh` — CLI script to add A + AAAA DNS records to PiHole via the v6 REST API
- **Updated:** `ARCHITECTURE.md` — added `## 🔧 Scripts & Tooling` section documenting the script

## Why it was changed
Manually creating DNS records via the PiHole web UI every time a new service is added is tedious and error-prone. This script automates the process, keeping it consistent with the GitOps-lite workflow.

## How it works
1. Accepts a service name as `$1` (e.g. `jellyfin`)
2. Resolves the PiHole API password from `$PIHOLE_PASSWORD` env var or `infrastructure/dns/.env`
3. Authenticates with the PiHole v6 API at `http://192.168.86.27` → obtains a session SID
4. PUTs an A record via `PUT /api/config/dns/hosts/<ip%20domain>`: `<service>.pippinn.me → 192.168.86.17`
5. PUTs an AAAA record the same way: `<service>.pippinn.me → 2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362`
6. Logs out (DELETE `/api/auth`) via a trap on exit

## New secrets/variables created
None. The script reuses the existing `FTLCONF_webserver_api_password` from `infrastructure/dns/.env`.

## ARCHITECTURE.md update required?
Yes — done. Added `## 🔧 Scripts & Tooling` section.

## global.env update required?
No.
