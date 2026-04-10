# Battery Reminder — Summary

## What was changed
- Created `/config/packages/battery_reminder.yaml` containing:
  - `input_number.battery_low_threshold` — configurable alert threshold (default 20%, range 5–50%)
  - `group.battery_monitor_exclusions` — phone sensors excluded from monitoring (`sensor.pixel_7_battery_level`, `sensor.pixel_7a_battery_level`)
  - `sensor.devices_with_low_battery` — template sensor exposing count, device names, and levels of currently-low devices
  - `script.battery_send_notification` — sends consolidated push notification via `notify.grimur_mobile_phones`
  - `automation.battery_low_on_change` — real-time alert on threshold crossing, suppressed 23:00–08:05
  - `automation.battery_daily_check` — morning sweep at 08:05, catches overnight drops missed during quiet hours

## Why it was changed
Provide proactive battery replacement reminders for ZHA/Zigbee devices before they fail silently.

## Key design decisions
- **`event: state_changed` trigger** — fully dynamic, no entity list to maintain, new ZHA devices covered immediately without any reload
- **Exclusion group** — phone companion-app battery sensors excluded via `group.battery_monitor_exclusions`; edit the group and `Reload Groups` to add/remove devices, no restart needed
- **`<=` threshold** — a device at exactly the threshold value is treated as low, consistently across all four template blocks
- **Zero-pad sort** — `"%03d" | format(level)` used as sort key so 9% sorts before 10%, not after 80%
- **Quiet hours 23:00–08:05** — real-time alert suppressed overnight; daily 08:05 check acts as deferred delivery

## Tests passed
- ✅ Test 1 — Helpers loaded correctly
- ✅ Test 2 — Template sensor counts correctly
- ✅ Test 5 — Notification script delivers to `notify.grimur_mobile_phones`
- ✅ Test 8 — Real-time alert fires on threshold crossing
- ✅ Test 9 — Dead battery (0%) triggers alert
- ✅ Test 11 — Already-low device does not re-notify
- ✅ Test 12 — Device re-arms after battery recovery
- ✅ Test 13 — Excluded phone sensors produce no notification

## New secrets / variables created
None. `notify.grimur_mobile_phones` was a pre-existing notify group.

## Architecture / global.env updates required
None. No new ports, volumes, or network changes.

## Lovelace card
Not yet added. YAML is in `plan.md` — paste into the UI editor on any dashboard view when ready.
