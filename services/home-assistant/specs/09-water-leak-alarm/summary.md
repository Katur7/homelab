# HA-09: Water Leak Alarm — Summary

## What Changed
Created [`services/home-assistant/config/packages/water_leak_alarm.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/water_leak_alarm.yaml) and documented the design in [`services/home-assistant/specs/09-water-leak-alarm/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/09-water-leak-alarm/plan.md).

## Why
Water leaks require immediate attention, but raw sensor triggers produce unwanted notifications during manual sensor testing or battery replacements. This package introduces a 15-second grace period before sounding an emergency alarm, repeats alerts every 10 minutes until resolved, allows muting from the dashboard, and automatically clears and resets when sensors are dry.

## How It Works
- **Dynamic Monitoring**: Monitors all binary sensors with `device_class: moisture` (excluding any in `group.water_leak_exclusions`).
- **15-Second Grace Period**: Suppresses alerts if a test event finishes within 15 seconds.
- **Critical Alerts**: Dispatches to `notify.grimur_mobile_phones` with critical sound, max volume, and DND bypass.
- **Repeat Reminders**: Evaluates every minute and resends critical alerts every 10 minutes while leaks persist.
- **Dashboard Mute**: `input_boolean.water_leak_muted` suppresses repeat alerts, auto-resetting to `off` once all sensors dry.
- **Resolution & Debounce**: Sends a normal-priority notification 5 seconds after drying (only if the sensor was wet $\ge 15\text{s}$).
- **Reboot Resilience**: Checks for active leaks 30 seconds after Home Assistant boots.
