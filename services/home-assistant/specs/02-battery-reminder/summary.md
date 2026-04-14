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

## Post-deployment fixes

### Fix 1 — ZHA sleep/wake repeat notifications (2026-04-13)
**Problem:** ZHA devices that go `unavailable` on sleep and wake up with a low battery value were re-triggering the real-time alert on every wake cycle. The original condition treated `old_state = unavailable` as `float(100)`, making every `unavailable → low` transition look like a fresh crossing from above threshold.

**Fix:** Require `old_state` to be a real numeric value strictly above threshold. Any `old_state` that is `none`, `unavailable`, or `unknown` suppresses the alert. New devices that have never reported before are caught by the 08:05 daily check.

**Condition change:**
```yaml
# Before
and (trigger.event.data.old_state is none
     or trigger.event.data.old_state.state | float(100)
        > states('input_number.battery_low_threshold') | float(20))

# After
and trigger.event.data.old_state is not none
and trigger.event.data.old_state.state not in ['unavailable', 'unknown']
and trigger.event.data.old_state.state | float(-1)
   > states('input_number.battery_low_threshold') | float(20)
```

---

### Fix 2 — eInkFrame boot-artifact 0% readings (2026-04-14)
**Problem:** The eInkFrame reports `0%` for ~3 minutes during each boot/wake cycle before stabilising on its real value. History confirmed the pattern: `unavailable → unknown → 0.0` (×3), then gradual climb to real charge level. The daily check at 08:05 would include the device if it happened to be mid-boot at that time, sending a false low-battery notification.

**Fix:** Added a 10-minute persistence guard to the daily check — a device is only included if its low state has been stable for more than 600 seconds (`(now() - s.last_changed).total_seconds() > 600`). Boot artifacts (~3 min) are filtered; genuine dead batteries (hours) are not.

---

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
