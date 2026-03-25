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
