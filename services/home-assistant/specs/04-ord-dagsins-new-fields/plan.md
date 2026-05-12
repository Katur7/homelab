# Spec 04 — Orð Dagsins: Accept Header + New Fields

## Context
The upstream `ord-dagsins` server at `https://ord-dagsins.pippinn.me` returns JSON for `GET /`.
Today it gates JSON output on `Content-Type: application/json` (a server-side bug).
After a server-side fix it will gate on `Accept: application/json` instead.
The response schema also gains three new fields: `pos`, `gender`, `stuttbeyg`.

## Changes

### 1. `services/home-assistant/config/sensors/word_of_the_day.yaml`
- Add `Accept: application/json` alongside the existing `Content-Type` header.
  Keep `Content-Type` so the integration keeps working against the current (unfixed) server.
- Add `pos`, `gender`, `stuttbeyg` to `json_attributes`.

### 2. `services/home-assistant/config/templates/word_of_the_day.yaml`
- Add template sensors for `pos`, `gender`, `stuttbeyg`.
- `gender` and `stuttbeyg` can be `null` in the JSON — handle gracefully (return `None`
  when attribute is none, matching existing pattern for missing examples).
- Do not translate or map `pos`/`gender` codes — pass through as-is.

## New fields reference
| Field      | Type          | Notes |
|------------|---------------|-------|
| pos        | string        | Part-of-speech code. Always present. |
| gender     | string\|null  | Grammatical gender, null for non-nouns. |
| stuttbeyg  | string\|null  | Short inflection hint, null when absent. |

## Rollback
Revert both YAML files. Server still responds to `Content-Type` so dropping `Accept` is safe.

## Out of scope
- Endpoint URL / query params unchanged.
- No error handling changes.
- No test fixtures (integration is HA YAML, no test suite in this repo).
