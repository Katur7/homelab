# HA-11: Expected Rain Sensor Overhaul

## Context
[`services/home-assistant/config/templates/expected_rain.yaml`](../../config/templates/expected_rain.yaml) reported `0` nearly all the time due to compounding defects:
1. **Formula cancellation:** Weighted rainfall ($\sum \text{mm}_i \times p_i$) was divided by `total_rain` ($\sum \text{mm}_i$), cancelling out `mm` and returning a `0.0–1.0` fraction rounded to 1 decimal.
2. **Deterministic `0 mm` short-circuit:** `total_rain == 0` forced `0`, ignoring Tomorrow.io ensemble `precipitation_probability` (`15–40%`) on light/uncertain rain hours.
3. **Shrinking window & UTC date bug:** Filtering by `today` via string match against UTC `datetime` misclassified midnight local hours (`Europe/Stockholm`) and shrank to 1–2 hours late in the evening.
4. **Missing triggers & metadata:** Polled only every 2h (`hours: /2`) with no startup/reload trigger, `unit_of_measurement`, `state_class`, or null guards.

*Note on weather provider:* SMHI (`weather.smhi_*`) was evaluated first, as preferred for Nordic forecasts, but Home Assistant's `smhi` integration does not expose `precipitation_probability` in `weather.get_forecasts`. `weather.tomorrow_io_home_daily` (`type: hourly`) is retained.

---

## Changes

### [`services/home-assistant/config/templates/expected_rain.yaml`](../../config/templates/expected_rain.yaml)

1. **Triggers & Guard Condition:**
   - Poll hourly (`hours: /1`), on `homeassistant` `start`, on `event_template_reloaded`, and when `weather.tomorrow_io_home_daily` recovers from `unavailable`/`unknown`.
   - Gate execution on `states('weather.tomorrow_io_home_daily') not in ['unavailable', 'unknown']` (`weather.get_forecasts` reads Tomorrow.io's coordinator cache — zero extra cloud API calls).

2. **Single-Pass Window Calculation (`actions` → `variables`):**
   - Convert forecast timestamps to local timezone (`as_datetime | as_local`) and discard past hours (`dt >= now().replace(minute=0, second=0, microsecond=0)`).
   - Anchor rolling `12h` and `24h` windows to the first current/upcoming forecast step (`ns.anchor`), alongside local `today` (`dt.date() == local_today`).
   - Null-guard `precipitation` (`float(0)`) and `precipitation_probability` (`float(0) | round(0) | int(0)`).

3. **Sensor State & Attributes (`sensor.expected_rain`):**
   - **Primary `state`:** Maximum `precipitation_probability` (`0–100`, `unit_of_measurement: "%"`, `state_class: measurement`) over the **rolling next 12 hours**.
   - **`availability`:** `true` when at least one valid entry exists in the next-12h window.
   - **`attributes`:**

| Attribute | Unit / Type | Description |
|---|---|---|
| `precipitation_next_12h_mm` | `float` (`mm`) | Unweighted total rainfall over next 12h |
| `expected_next_12h_mm` | `float` (`mm`) | Probability-weighted rainfall ($\sum \text{mm}_i \times p_i$) over next 12h |
| `precipitation_today_mm` | `float` (`mm`) | Unweighted remaining rainfall today (local date) |
| `precipitation_next_24h_mm` | `float` (`mm`) | Unweighted total rainfall over next 24h |
| `probability_today_pct` | `int` (`%`) | Max rain probability for remaining hours today |
| `probability_next_24h_pct` | `int` (`%`) | Max rain probability over next 24h |
| `next_rain_at` | `string\|null` | Local ISO-8601 timestamp of next hour (within 24h) with `mm >= 0.1` or `prob >= 40` |

---

## Impact on Other Services
- **E-ink Display (`photoframe`):** Downstream display reads `sensor.expected_rain` (previously `0.0–1.0` state + `max_precipitation_probability` `0.0–1.0` attribute). Display template/renderer will need a follow-up update to consume `0–100%` state and the new `_mm` / `_pct` attributes.
- **Home Assistant Recorder:** Sensor previously lacked `state_class`, so adding `unit_of_measurement: "%"` and `state_class: measurement` introduces numeric graphing cleanly with no Long-Term Statistics unit-mismatch conflict.

---

## Validation
1. Validate YAML syntax locally.
2. Sync/pull on NAS and run **Developer Tools → YAML → Check Configuration**, then **Reload Template Entities**.
3. Verify `sensor.expected_rain` state (`0–100 %`) and attributes under **Developer Tools → States**.

---

## Rollback
Revert [`services/home-assistant/config/templates/expected_rain.yaml`](../../config/templates/expected_rain.yaml) via `git checkout HEAD -- services/home-assistant/config/templates/expected_rain.yaml` and reload template entities in Home Assistant.
