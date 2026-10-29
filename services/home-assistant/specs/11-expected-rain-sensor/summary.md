# HA-11: Expected Rain Sensor Overhaul — Summary

## What Changed
- Overhauled [`services/home-assistant/config/templates/expected_rain.yaml`](../../config/templates/expected_rain.yaml).
- Added specification in [`services/home-assistant/specs/11-expected-rain-sensor/plan.md`](./plan.md).

## Why
`sensor.expected_rain` previously divided probability-weighted rainfall by total rainfall (`ns.weighted / total_rain`), cancelling `mm` into a `0.0–1.0` fraction, short-circuiting to `0` whenever deterministic `precipitation` was `0` (even when `precipitation_probability > 0`), and filtering by UTC date string on a shrinking `today` window.

## How It Works
- **Primary State:** Max `precipitation_probability` (`0–100`, `unit_of_measurement: "%"`, `state_class: measurement`) across the rolling next 12 hours from `weather.tomorrow_io_home_daily` (`type: hourly`).
- **Triggers:** Hourly (`hours: /1`), `homeassistant` `start`, `event_template_reloaded`, and recovery of `weather.tomorrow_io_home_daily` from `unavailable`/`unknown`.
- **Attributes:** `precipitation_next_12h_mm`, `expected_next_12h_mm`, `precipitation_today_mm`, `precipitation_next_24h_mm`, `probability_today_pct`, `probability_next_24h_pct`, and `next_rain_at` (all timezone-aware via `as_local` and null-guarded).

## Secrets & Architecture Updates
- **New secrets / environment variables:** None.
- **`ARCHITECTURE.md` / `global.env` updates required:** None.
- **Follow-up:** Update e-ink display (`photoframe`) consumer to use the `0–100%` state and `_mm` / `_pct` attributes.
