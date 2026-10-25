# HA-06: Awning Controller — Summary

## What Changed
- Created [`services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js): Local Shelly Plus 2PM mJS wind safety monitor and telemetry script.
- Created [`services/home-assistant/config/packages/awning_controller.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/awning_controller.yaml): Home Assistant package containing helpers, template sensors, and automations.
- Documented the architecture and commissioning guide in [`services/home-assistant/specs/06-awning-controller/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/06-awning-controller/plan.md).

## Why
Replaced the decommissioned Somfy Soliris Uno controller with a Shelly Plus 2PM and Shelly Plus Add-on connected to the existing Somfy Soliris sun/wind sensor and outside motor relay box. High-wind retraction must execute locally on the Shelly independent of Wi-Fi or Home Assistant, while Home Assistant manages sunlight comfort automations and manual override state.

## How It Works
- **Cover Profile (Time-Based Limits)**: Configured in `Cover` mode with 22-second open/close duration limits (`maxtime_open` / `maxtime_close`) and obstacle detection disabled to accommodate the intermediate motor relay box.
- **Local Wind Telemetry (`shelly-wind-safety.js`)**:
  - Counts reed switch pulses on `input:100` with a 15 ms software debounce over a 2-second sliding window.
  - Currently runs in passive telemetry-only mode (no relay switching) while wiring and sensor baselines are being verified.
  - Emits `wind_telemetry` events via `Shelly.emitEvent()` only when pulse count changes, avoiding logbook spam.
- **Home Assistant Package (`awning_controller.yaml`)**:
  - Maps `event.awning_wind_safety` attributes (`locked`, `pulses`) to `binary_sensor.awning_wind_lockout` and `sensor.awning_wind_pulses`.
  - Automatically retracts the awning 30 minutes after sunset if it is extended (`closed`).
  - Raw `event.awning_wind_safety` entity is excluded from the logbook in `configuration.yaml` to keep the Activity view clean.

