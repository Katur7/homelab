# Infrastructure Quirks & Non-Obvious Fixes

A record of non-trivial issues and their resolutions. These are things that are
not obvious from the code or config alone, and that would be painful to
rediscover from scratch.

---

## Q1: Chrome QUIC Errors — Traefik HTTP/3

**Symptom:** Chrome shows connection errors or falls back to HTTP/2 with console
warnings like `ERR_QUIC_PROTOCOL_ERROR` or `net::ERR_HTTP2_PROTOCOL_ERROR`.
Chrome aggressively probes for HTTP/3 (QUIC over UDP/443) and will report errors
if the server doesn't respond correctly.

**Fix:** Enable HTTP/3 on the `websecure` entrypoint in
[infrastructure/gateway/config/traefik.yml](infrastructure/gateway/config/traefik.yml):

```yaml
entryPoints:
  websecure:
    address: :443
    http3: {}   # <-- this line
```

**Why it works:** Traefik will now listen on UDP/443 for QUIC connections and
advertise HTTP/3 support via the `Alt-Svc` response header. Chrome honours this
and connects cleanly instead of probing a port that produces no response.

**Side notes:**
- UDP/443 must be open on the host firewall / any upstream router NAT rules.
- The `http3: {}` block can be extended with `advertisedPort` if the public
  port differs from the internal one (e.g. behind a NAT that maps 443→8443).
- Other browsers (Firefox, Safari) also benefit but are less aggressive about
  reporting the absence of HTTP/3.

---

## Q2: Android SSL Handshake Failures — Pi-hole HTTPS Record Block

**Symptom:** Android clients (phones, tablets) fail to open services on
`*.pippinn.me` with an SSL handshake error. Desktop browsers and iOS are
unaffected. The failure is intermittent and hard to reproduce without packet
capture.

**Fix:** Add the following as a **regex deny** rule in Pi-hole (Domains →
Regex filter):

```
^.*\.pippinn\.me$;querytype=HTTPS
```

**Why it works:** Modern Android resolvers issue DNS `HTTPS` record queries
(record type 65, defined in RFC 9460) alongside regular `A`/`AAAA` lookups.
An `HTTPS` record can advertise ALPN tokens (`h3`, `h2`) and other connection
parameters. When Android receives a positive `HTTPS` response it immediately
attempts to negotiate the advertised protocol — including HTTP/3 over QUIC. If
the QUIC handshake stalls or fails (e.g. UDP is blocked on the client's
network, or there is an asymmetric NAT), Android does **not** transparently
fall back; it surfaces the failure as an SSL error.

Blocking the `HTTPS` query type at the DNS layer causes the resolver to return
`NXDOMAIN` (or no answer) for those record types only. Android then falls back
to a plain TCP/TLS connection with standard ALPN negotiation, which works
reliably.

**Pi-hole location:** Pi-hole admin UI → **Domains** → **Regex filter** →
**Add Regex** (Deny).

**Scope of the rule:** The regex `^.*\.pippinn\.me$` matches every subdomain
but not the apex `pippinn.me` itself. Adjust if needed.

**Side notes:**
- This rule does not affect `A`/`AAAA` lookups; DNS resolution is normal.
- Desktop Linux/macOS and iOS handle QUIC fallback more gracefully and are not
  affected.
- The `;querytype=HTTPS` suffix is Pi-hole FTL v6+ syntax for matching on a
  specific DNS record type within a regex rule.
- If HTTP/3 ever becomes fully reliable end-to-end (stable UDP path, no NAT
  issues), this rule can be removed and Android will use QUIC cleanly.

---

## Q3: Traefik Cannot Reach Host-Network Services — `host.docker.internal` on Linux

**Symptom:** Traefik returns `502 Bad Gateway` when proxying to a service running
directly on the host (e.g. Home Assistant in `network_mode: host`). The backend
URL uses the hostname `host.docker.internal`, which resolves fine on Docker
Desktop (Mac/Windows) but **does not exist by default on Linux**.

**Affected service:** Home Assistant (runs on the host network, not in a
container on `traefik_internal`).

**Fix:** Add an `extra_hosts` entry to the Traefik container in
[infrastructure/gateway/compose.yaml](infrastructure/gateway/compose.yaml):

```yaml
extra_hosts:
  - host.docker.internal:172.17.0.1
```

`172.17.0.1` is the IP of the `docker0` bridge interface on the host — the
address the host is reachable at from inside any container.

**Why it works:** On Linux, Docker does not inject `host.docker.internal` into
container `/etc/hosts`. The `extra_hosts` entry does it manually. Traefik can
then resolve the hostname and forward traffic to services bound to the host
network stack.

**Side notes:**
- `172.17.0.1` is the default `docker0` bridge IP. Verify with
  `ip addr show docker0` if your host differs.
- This entry only needs to exist in the Traefik container — other containers
  that don't need to reach host-network services do not require it.
- If HA is ever moved into a Docker network (e.g. `traefik_internal`), this
  entry becomes redundant and can be removed.

---

## Q4: Android Chrome Intercepts Passkey Creation — Cannot Save to Bitwarden

**Symptom:** When registering a passkey on Authelia from Android Chrome, Chrome
always intercepts the WebAuthn `navigator.credentials.create()` call and presents
its own passkey manager (Google Password Manager). There is no option to redirect
to a third-party provider such as Bitwarden. The passkey cannot be saved to
Bitwarden on Android Chrome.

**Status: No fix found.** The Authelia passkey is stored in Chrome's built-in
passkey manager (synced via Google account) rather than Bitwarden.

**Root cause:** Android's FIDO2 credential provider model changed in Android 14.
Prior to that, Chrome on Android exclusively used its own passkey manager with no
way to delegate to a third-party. Android 14+ introduced the Credential Manager
API which *should* allow choosing a provider (Bitwarden, 1Password, etc.), but
Chrome's passkey sheet does not always surface the provider picker — particularly
on first registration — and falls back silently to Google Password Manager.

**Workarounds tried:** None resolved the issue. Potential avenues if revisiting:
- Ensure Bitwarden is set as the **default** autofill and passkey provider in
  Android Settings → Passwords & Accounts → Preferred service.
- Use **Firefox for Android** instead of Chrome — Firefox delegates to the system
  Credential Manager picker more reliably.
- Use the **Bitwarden app's built-in browser** to trigger the passkey registration.

**Current state:** The Authelia passkey lives in Chrome/Google Password Manager.
Login from Android works; it just isn't portable to Bitwarden.

---
