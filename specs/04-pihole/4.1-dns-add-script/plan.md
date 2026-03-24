# Plan: PiHole DNS Add Script + Architecture Update

## Context
The homelab uses PiHole v6 (at `192.168.86.27`) for local DNS. Adding new services requires
manually creating DNS records via the PiHole web UI. A CLI script using the PiHole v6 API
will automate this, following GitOps-lite conventions. The script will always create both
an A record (IPv4) and an AAAA record (IPv6) for `<service>.pippinn.me`.

## Deliverables
1. `scripts/add-dns.sh` — shell script using PiHole v6 API
2. Update to `ARCHITECTURE.md` — note the script under a new Scripts & Tooling section

---

## Script: `scripts/add-dns.sh`

### Behaviour
- Accept service name as `$1` (e.g. `jellyfin` → `jellyfin.pippinn.me`)
- Hardcode target IPs: `192.168.86.17` (A) and `2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362` (AAAA)
- Authenticate with PiHole v6 API → obtain session token (SID)
- POST both DNS records
- Delete session (logout)
- Print clear success/failure per record

### Password resolution (in order)
1. `$PIHOLE_PASSWORD` env var
2. Parse from `infrastructure/dns/.env` (key: `FTLCONF_webserver_api_password`)

### PiHole v6 API calls (base URL: `http://192.168.86.27`)

| Step | Method | Endpoint | Body |
|------|--------|----------|------|
| Login | POST | `/api/auth` | `{"password": "<pw>"}` |
| Add A | POST | `/api/customdns` | `{"domain": "<svc>.pippinn.me", "ip": "192.168.86.17"}` |
| Add AAAA | POST | `/api/customdns` | `{"domain": "<svc>.pippinn.me", "ip": "2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362"}` |
| Logout | DELETE | `/api/auth` | — (requires `X-FTL-SID` header) |

Authentication: the login response returns `{"session": {"sid": "..."}}` — pass as `X-FTL-SID` header on subsequent requests.

### Dependencies
- `curl`
- `jq`

---

## Architecture Update: `ARCHITECTURE.md`

Add a new `## 🔧 Scripts & Tooling` section at the end of the file:

```markdown
## 🔧 Scripts & Tooling

### `scripts/add-dns.sh` — Add Local DNS Record
Adds an A + AAAA record for `<service>.pippinn.me` to PiHole via the v6 REST API.
Points to the NAS/Traefik gateway: IPv4 `192.168.86.17`, IPv6 `2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362`.

**Usage:**
./scripts/add-dns.sh <service-name>
# Example: ./scripts/add-dns.sh jellyfin
# → Creates jellyfin.pippinn.me → 192.168.86.17 + 2001:9b1:c5c0:7e00:16da:e9ff:fe68:6362

**Password:** Set $PIHOLE_PASSWORD env var, or the script auto-reads infrastructure/dns/.env.
```

---

## Critical Files
- New: `scripts/add-dns.sh`
- Edit: `ARCHITECTURE.md`

## Verification
1. Run `./scripts/add-dns.sh testservice` — verify output shows both records added
2. Check PiHole UI (or `curl http://192.168.86.27/api/customdns`) for `testservice.pippinn.me`
3. `dig testservice.pippinn.me @192.168.86.27` → should resolve to both IPs
4. Clean up test record via PiHole UI
