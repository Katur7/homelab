# Milestone 07.1 Summary: Traefik Access Log Format → JSON

**Date:** 2026-03-29
**Status:** `COMPLETE`

---

## What Was Changed

`infrastructure/gateway/config/traefik.yml` — `accesslog.format: common` → `accesslog.format: json`

## Why

Apache CLF (`common`) only records the path portion of the request line (e.g. `GET /dashboard HTTP/1.1`).
Switching to JSON captures all access log fields including `RequestHost`, `RouterName`, `ServiceName`,
TLS cipher/version, durations, and retry counts — making log analysis and CrowdSec correlation
significantly more effective.

## Outcome

- Traefik restarted cleanly (no errors).
- Access log immediately switched to JSON lines, each containing `RequestHost`, `RouterName`,
  `ServiceAddr`, `TLSVersion`, etc.
- CrowdSec continued to process logs without issue — the installed `crowdsecurity/traefik-logs`
  parser supports both CLF and JSON natively (two sibling parser nodes).

## No Architecture / global.env Changes Required

The access log format is an internal Traefik setting. No downstream services or env vars are affected.

## Deviations from Plan

None.
