# Summary — Spec 04: Orð Dagsins new fields

## What changed
- `sensors/word_of_the_day.yaml`: added `Accept: application/json` header; added `pos`, `gender`, `stuttbeyg` to `json_attributes`.
- `templates/word_of_the_day.yaml`: added template sensors `word_of_the_day_pos`, `word_of_the_day_gender`, `word_of_the_day_stuttbeyg`.

## Why
Server gains `pos`/`gender`/`stuttbeyg` fields. `Accept` header prepares the integration for the server-side fix that will switch JSON gating from `Content-Type` to `Accept`; `Content-Type` kept for backward compat with the current server.

## Null handling
`gender` and `stuttbeyg` may be `null` — template sensors return `None` in that case, matching existing pattern.

## New secrets/variables
None.

## Architecture/global.env update needed?
No.
