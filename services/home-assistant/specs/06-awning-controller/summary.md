# HA-06: Awning Controller — Summary

## What Changed
- Created [`services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js): Local Shelly Plus 2PM mJS wind safety monitor and telemetry script.
- Created [`services/home-assistant/config/packages/awning_controller.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/awning_controller.yaml): Home Assistant package containing helpers, template sensors, and automations.
- Documented the architecture and commissioning guide in [`services/home-assistant/specs/06-awning-controller/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/06-awning-controller/plan.md).

## Why
Replaced the decommissioned Somfy Soliris Uno controller with a Shelly Plus 2PM and Shelly Plus Add-on connected to the existing Somfy Soliris sun/wind sensor and outside motor relay box. High-wind retraction must execute locally on the Shelly independent of Wi-Fi or Home Assistant, while Home Assistant manages sunlight comfort automations and manual override state.

## How It Works
- **Cover Profile (Time-Based Limits)**: Configured in `Cover` mode with 22-second open/close duration limits (`maxtime_open` / `maxtime_close`) and obstacle detection disabled to accommodate the intermediate motor relay box.
- **Local Wind Safety (`shelly-wind-safety.js`)**:
  - Counts reed switch pulses on `input:100` with a 15 ms software debounce over a 2-second sliding window.
  - Immediately executes `Cover.Close` locally when pulses reach $\ge 10$ per 2s window and activates a sliding 15-minute calm lockout (with a 60s boot grace period).
  - Emits `wind_lockout`, `wind_clear`, and 10-second `wind_telemetry` events via `Shelly.emitEvent()` to `event.awning_wind_safety`.
- **Home Assistant Package (`awning_controller.yaml`)**:
  - Maps `event.awning_wind_safety` attributes (`locked`, `pulses`) to `binary_sensor.awning_wind_lockout` and `sensor.awning_wind_pulses`.
  - Auto-extends `cover.outdoor_shelly_markiser_awning` when `sensor.outdoor_shelly_markiser_awning_somfy_sun_sensor_analogue` exceeds `input_number.awning_sun_threshold_extend` for 10 minutes during active hours.
  - Auto-retracts when sunlight stays below `input_number.awning_sun_threshold_retract` for 20 minutes, at sunset, or at the end of active hours.
  - Detects manual daytime retraction (`input_boolean.awning_manual_override`) to prevent automatic re-extension until midnight or manual reopening.
  - Includes a watchdog automation that logs a warning if the 10-second `event.awning_wind_safety` heartbeat stops updating for $> 5$ minutes.
