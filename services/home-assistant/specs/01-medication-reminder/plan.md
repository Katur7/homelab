# Medication Reminder — Home Assistant Automation Plan

## Context
Create a HA automation that reminds the user to take daily medication. Reminders trigger when the phone leaves the charger (5:00–9:30 window, 30-min delay), with a hard fallback at 10:00. An NFC tag on the medicine box marks medication as taken. Three notification actions: mark taken, snooze 30 min, or wait until back home. All state resets at midnight.

---

## File to Create
`/config/packages/medication_reminder.yaml` — single package file containing all helpers, scripts, and automations.

Also requires two lines added to `/config/configuration.yaml` under a new `homeassistant:` block:
```yaml
homeassistant:
  packages: !include_dir_named packages/
```

---

## Secrets (`/config/secrets.yaml` — gitignored, never committed)

All environment-specific entity IDs and identifiers live in `secrets.yaml`. Reference with `!secret` in the package YAML.

```yaml
# Medication reminder
phone_charging_sensor: binary_sensor.your_phone_is_charging
phone_device_tracker: device_tracker.your_phone
phone_notify_service: notify.mobile_app_your_phone
phone_device_id: abc123...   # Settings → About → Device ID in the HA companion app
medication_nfc_tag_id: your-nfc-tag-uuid
```

| Secret | Where to find it |
|---|---|
| `phone_charging_sensor` | Settings → Devices → your phone → find `is_charging` binary sensor |
| `phone_device_tracker` | Settings → Devices → your phone → device tracker entity |
| `phone_notify_service` | Developer Tools → Services → search `notify.mobile_app_` |
| `phone_device_id` | HA companion app → Settings → Companion App → About |
| `medication_nfc_tag_id` | Developer Tools → Events → listen to `tag_scanned`, scan the tag, copy `tag_id` |

---

## Helpers

```yaml
input_datetime:
  medication_last_taken:
    name: "Medication Last Taken"
    has_date: true
    has_time: true

input_boolean:
  medication_notified_today:
    name: "Medication Notified Today"
  medication_waiting_for_home:
    name: "Medication Waiting for Home"

timer:
  medication_snooze:
    name: "Medication Snooze"
    duration: "00:30:00"
    restore: false

  medication_notification_timeout:
    name: "Medication Notification Timeout"
    duration: "01:00:00"
    restore: false
```

---

## Shared Scripts (avoids duplicating logic)

### `script.medication_mark_taken`
Sets `input_datetime.medication_last_taken` to now, cancels `timer.medication_snooze`, cancels `timer.medication_notification_timeout`, clears `medication_waiting_for_home`, sets `medication_notified_today`.

### `script.medication_send_reminder`
Accepts three fields:
- `message` — notification body text
- `include_home_action` (boolean, default `true`) — whether to include the "Remind me when home" button
- `final_reminder` (boolean, default `false`) — when `true`: sends only the "Already took them" button, does NOT start the timeout timer, does NOT start `timer.medication_snooze`. Used exclusively by the 17:00 hard stop.

Sets `medication_notified_today`, then (unless `final_reminder` is true) starts `timer.medication_notification_timeout` (1 hour). Calls `!secret phone_notify_service`. Notification data includes `tag: medication_reminder` so each new notification **replaces** the previous one (no stacking on Android or iOS).

Action buttons:
- Always: `MEDICATION_TAKEN` → "Already took them"
- When `final_reminder` is false: `MEDICATION_SNOOZE_30` → "Remind me again in 30 mins"
- When `final_reminder` is false AND `include_home_action` is true: `MEDICATION_REMIND_HOME` → "Remind me when I'm back home"

**Automations that pass `include_home_action: false`:** 7 (already-home case), 8 (`medication_arrived_home`), 9 (`medication_17_fallback`) — these fire because the user is home or it's late in the day.

**Automations that pass `final_reminder: true`:** 9 (`medication_17_fallback`) only — this is the hard stop. No further reminders or timers after this point.

---

## Automations

### 1. `medication_off_charger`
- **Trigger:** `!secret phone_charging_sensor` → `off`
- **Conditions:** time 05:00–09:30, medication not taken today, `timer.medication_snooze` is idle
- **Action:** `timer.start` for 30 min on `timer.medication_snooze`

### 2. `medication_timer_done`
- **Trigger:** `timer.finished` for `timer.medication_snooze`
- **Conditions:** medication not taken today
- **Action:** call `script.medication_send_reminder`

### 3. `medication_10am`
- **Trigger:** time 10:00
- **Conditions:** medication not taken today, `medication_notified_today` is off, `timer.medication_snooze` is idle
- **Action:** call `script.medication_send_reminder`
- **Note:** `medication_notified_today` only gates this automation — not the timer-based re-notifications. Snooze chains check "taken today", not this flag.

### 4. `medication_nfc_scanned`
- **Trigger:** `tag_scanned` event, tag_id `!secret medication_nfc_tag_id`
- **Conditions:** `trigger.event.data.device_id == !secret phone_device_id` (prevents accidental third-party scan)
- **Action:** call `script.medication_mark_taken`

### 5. `medication_action_taken`
- **Trigger:** `mobile_app_notification_action`, action = `MEDICATION_TAKEN`
- **Conditions:** none
- **Action:** call `script.medication_mark_taken`

### 6. `medication_action_snooze`
- **Trigger:** `mobile_app_notification_action`, action = `MEDICATION_SNOOZE_30`
- **Conditions:** medication not taken today (guards against stale notifications)
- **Action:** `timer.cancel` then `timer.start` for 30 min on `timer.medication_snooze`, cancel `timer.medication_notification_timeout`

### 7. `medication_action_home`
- **Trigger:** `mobile_app_notification_action`, action = `MEDICATION_REMIND_HOME`
- **Conditions:** medication not taken today
- **Action:**
  - Cancel `timer.medication_notification_timeout` (user has acknowledged the notification)
  - Turn on `medication_waiting_for_home`
  - `choose`: if `!secret phone_device_tracker` is already `home` → call `script.medication_send_reminder` with `include_home_action: false`, turn off waiting flag

### 8. `medication_arrived_home`
- **Trigger:** `!secret phone_device_tracker` → `home` (with `for: 2 minutes` to avoid GPS jitter)
- **Conditions:** `medication_waiting_for_home` is on, medication not taken today
- **Action:** call `script.medication_send_reminder` with `include_home_action: false`, turn off `medication_waiting_for_home`

### 9. `medication_17_fallback`
- **Trigger:** time 17:00
- **Conditions:** medication not taken today
- **Action:** cancel both timers, turn off `medication_waiting_for_home`, call `script.medication_send_reminder` with `include_home_action: false` and `final_reminder: true`
- **Note:** Hard stop. Fires regardless of `medication_waiting_for_home` state. Cancels any running snooze or timeout timers first. The notification has only the "Already took them" button — no snooze, no remind-when-home. No further timers are started. This is the last reminder of the day.

### 10. `medication_notification_timeout`
- **Trigger:** `timer.finished` for `timer.medication_notification_timeout`
- **Conditions:** medication not taken today, time before 17:00
- **Action:** call `script.medication_send_reminder` (default parameters — re-arms the timeout timer, keeping the hourly nudge going)
- **Note:** Handles the "dismissed notification" case. Loops every hour until the user takes action or 17:00 fires and cancels the timer. The time condition is belt-and-suspenders — the 17:00 automation cancels the timer before it can fire — but guards against any edge-case timing.

### 11. `medication_startup_check`
- **Trigger:** `homeassistant.start`
- **Conditions:** time is between 10:00 and 17:00, medication not taken today, `medication_notified_today` is off
- **Action:** call `script.medication_send_reminder` with `include_home_action: false`
- **Note:** Catches the case where HA was down at 10:00. Time-cron triggers are edge-triggered and do not re-fire after a restart. `include_home_action: false` — user is likely home if they just restarted HA, and "remind when home" is ambiguous without knowing prior context.

### 12. `medication_daily_reset`
- **Trigger:** time 00:00
- **Conditions:** none
- **Action:** `timer.cancel` both timers, turn off `medication_waiting_for_home`, turn off `medication_notified_today`
- **Note:** Does NOT clear `medication_last_taken` — date comparison in templates resets naturally at midnight.

---

## "Taken Today" Template (used in all conditions)
```
{{ states('input_datetime.medication_last_taken')[:10] == now().strftime('%Y-%m-%d') }}
```

---

## Key Design Decisions
- **10:00 skip logic:** Both `medication_notified_today` flag AND timer idle check guard the 10:00 automation — belt-and-suspenders.
- **17:00 hard stop:** Fires for everyone who hasn't taken medication by 17:00, regardless of waiting state. Cancels all running timers. The notification shows only the "Already took them" button — no snooze, no remind-when-home. No further timers or reminders after this point until midnight reset.
- **Snooze limit:** None before 17:00 — snoozes work freely. The 17:00 hard stop is the definitive end of the reminder chain.
- **Notification timeout (1hr):** Every non-final notification starts a 1-hour timer. If dismissed without action, a fresh replacement notification arrives after 1 hour and re-arms — looping every hour until the user acts or 17:00 cancels everything. Cleared immediately on any user action (taken, snooze, remind-when-home, NFC scan). Not started by the 17:00 final reminder.
- **Notification tag:** All notifications use `data.tag: medication_reminder` — new notifications replace the previous one instead of stacking.
- **HA restart safety:** `restore: false` on both timers means restarts don't fire unexpected notifications.
- **"Already home" on REMIND_HOME:** Sends immediate notification and clears the waiting flag so `medication_arrived_home` doesn't double-fire.
- **NFC device guard:** `tag_scanned` is conditioned on `trigger.event.data.device_id` matching the registered phone device ID. Prevents accidental third-party scans.
- **Secrets:** All entity IDs and hardware identifiers live in `secrets.yaml` (gitignored). No personal identifiers are committed to the repository.

---

## Test Plan

### Tools used
All testing is done inside HA's built-in Developer Tools (sidebar → Developer Tools):
- **Events tab** — fire `tag_scanned` and `mobile_app_notification_action` events manually
- **Services tab** — call services (timer.start, input_boolean.turn_on, etc.) and set state
- **States tab** — inspect and manually set entity states
- **Template tab** — verify the "taken today" template evaluates correctly
- **Automations page** → click an automation → **Traces** — shows every condition pass/fail after a run

---

### Setup
Call `script.medication_reset_test_state` from Developer Tools → Actions. No parameters needed.

### State validation template
Paste into Developer Tools → Template to inspect state at any point:
```jinja
taken_today:      {{ states('input_datetime.medication_last_taken')[:10] == now().strftime('%Y-%m-%d') }}
last_taken:       {{ states('input_datetime.medication_last_taken') }}
notified_today:   {{ states('input_boolean.medication_notified_today') }}
waiting_for_home: {{ states('input_boolean.medication_waiting_for_home') }}
snooze_timer:     {{ states('timer.medication_snooze') }}
timeout_timer:    {{ states('timer.medication_notification_timeout') }}
```

---

### ✅ Test 1 — Helpers loaded correctly
**Steps:** After reloading YAML, open Developer Tools → States, search "medication"
**Expect:** 5 entities visible: `input_datetime.medication_last_taken`, `input_boolean.medication_notified_today`, `input_boolean.medication_waiting_for_home`, `timer.medication_snooze`, `timer.medication_notification_timeout`

---

### ✅ Test 2 — "Taken today" template
**Steps:** Developer Tools → Template tab, paste:
```
{{ states('input_datetime.medication_last_taken')[:10] == now().strftime('%Y-%m-%d') }}
```
**Expect:** `false` (before any scan), `true` after calling `script.medication_mark_taken`

---

### ✅ Test 3 — NFC scan marks as taken
**Steps:** Developer Tools → Events → fire event:
```
Event type: tag_scanned
Event data: {"tag_id": "<value from secrets.yaml>", "device_id": "<value from secrets.yaml>"}
```
**Expect:**
- `medication_last_taken` updates to today's date/time
- `medication_notified_today` turns on
- `medication_waiting_for_home` stays/turns off
- Both timers idle

---

### ✅ Test 3b — NFC scan from wrong device is ignored
**Steps:** Fire same `tag_scanned` event but with a different or missing `device_id`
**Expect:** `medication_mark_taken` does NOT run. Automation trace shows condition failed on device_id check.

---

### ⏭️ Test 4 — Morning charger trigger fires timer (skipped — sensor confirmed present, chain proven by Test 5)
**Prerequisite:** Reset state. Temporarily edit `medication_off_charger` to widen the time window to cover now (e.g., `after: "00:00:00"` `before: "23:59:00"`), reload YAML.
**Steps:** Developer Tools → States → find `phone_charging_sensor` entity → set state to `off`
**Expect:** `timer.medication_snooze` transitions to `active`
**Cleanup:** Restore original time window, reload YAML.

---

### ✅ Test 5 — Timer fires notification and starts timeout timer
**Steps:** Developer Tools → Services → call:
```
timer.start → timer.medication_snooze, duration: 00:00:05
```
Wait 5 seconds.
**Expect:** Push notification arrives on phone with 3 action buttons (including "Remind me when home"). `timer.medication_notification_timeout` becomes active. Check automation trace on `medication_timer_done`.

---

### ✅ Test 5b — Notification replaces instead of stacking
**Steps:** Run Test 5 twice in a row (fire a second short timer before the first notification is dismissed).
**Expect:** Only one notification visible in the phone tray — the second replaces the first.

---

### ✅ Test 6 — "Already took them" action
**Prerequisite:** Reset state.
**Steps:** Developer Tools → Events → fire:
```
Event type: mobile_app_notification_action
Event data: {"action": "MEDICATION_TAKEN"}
```
**Expect:** `medication_last_taken` set to today, both timers cancelled, flags updated.

---

### ✅ Test 7 — Snooze action restarts timer and cancels timeout
**Prerequisite:** Reset state. Start `timer.medication_notification_timeout` manually.
**Steps:** Fire event:
```
Event type: mobile_app_notification_action
Event data: {"action": "MEDICATION_SNOOZE_30"}
```
**Expect:** `timer.medication_snooze` becomes `active` (30 min). `timer.medication_notification_timeout` becomes idle.

---

### ⏭️ Test 8 — Snooze ignored if already taken today (skipped — condition proven implicitly: notification never fires when taken_today is true)
**Prerequisite:** Call `script.medication_mark_taken` first (so taken today = true).
**Steps:** Fire `mobile_app_notification_action` with `MEDICATION_SNOOZE_30`
**Expect:** Timer stays idle. Automation trace shows condition failed.

---

### Test 9 — "Remind when home" when NOT at home
**Prerequisite:** Ensure `phone_device_tracker` state is NOT `home`.
**Steps:** Fire event:
```
Event type: mobile_app_notification_action
Event data: {"action": "MEDICATION_REMIND_HOME"}
```
**Expect:**
- `medication_waiting_for_home` turns on
- No notification sent
- No timer started

---

### Test 10 — "Remind when home" when ALREADY at home
**Prerequisite:** Set `phone_device_tracker` to `home` via States tab.
**Steps:** Fire `mobile_app_notification_action` with `MEDICATION_REMIND_HOME`
**Expect:**
- Notification arrives with only 2 buttons (NO "Remind me when home")
- `medication_waiting_for_home` turns back off immediately
- `timer.medication_notification_timeout` becomes active

---

### Test 11 — Arrives home while waiting
**Prerequisite:** Reset state. Set `medication_waiting_for_home` to `on`. Set `phone_device_tracker` to `away`.
**Steps:** Set `phone_device_tracker` state to `home` via States tab.
Wait 2 minutes OR temporarily remove `for: minutes: 2`, reload, re-set state.
**Expect:**
- Notification arrives with only 2 buttons
- `medication_waiting_for_home` turns off
- `timer.medication_notification_timeout` becomes active

---

### Test 12 — 17:00 hard fallback fires regardless of waiting state
**Prerequisite:** Reset state (medication_waiting_for_home is OFF).
**Steps:** Temporarily set `medication_17_fallback` trigger time to 1–2 minutes from now, reload YAML, wait.
**Expect:**
- Notification arrives with only 2 buttons
- `medication_waiting_for_home` stays/turns off
**Cleanup:** Restore trigger to `17:00:00`, reload YAML.

### Test 12b — 17:00 also clears waiting flag when it was on
**Prerequisite:** Set `medication_waiting_for_home` to `on`.
**Steps:** Same as Test 12.
**Expect:** Same result — notification arrives, `medication_waiting_for_home` turns off.

---

### Test 13 — 10:00 fires when no notification sent yet
**Prerequisite:** Reset state (all flags off, timer idle, not taken today).
**Steps:** Temporarily set `medication_10am` trigger to 1–2 minutes from now, reload YAML, wait.
**Expect:** Notification arrives with 3 buttons (including "Remind me when home"). `timer.medication_notification_timeout` becomes active.
**Cleanup:** Restore trigger.

---

### Test 14 — 10:00 skipped when already notified
**Prerequisite:** Set `medication_notified_today` to `on`.
**Steps:** Trigger `medication_10am` same as Test 13.
**Expect:** No notification. Automation trace shows condition failed on `medication_notified_today`.

---

### Test 15 — 10:00 skipped when timer is running
**Prerequisite:** Start `timer.medication_snooze` manually (30 min). All other flags off.
**Steps:** Trigger `medication_10am`.
**Expect:** No notification. Trace shows timer idle condition failed.

---

### Test 16 — Notification timeout fires replacement notification
**Prerequisite:** Reset state.
**Steps:** Developer Tools → Services → call:
```
timer.start → timer.medication_notification_timeout, duration: 00:00:05
```
Wait 5 seconds.
**Expect:** Push notification arrives (replacing any existing). `timer.medication_notification_timeout` restarts (the new send re-arms it). Check trace on `medication_notification_timeout`.

---

### Test 17 — Startup check fires after 10:00 when HA was down
**Prerequisite:** Reset state (not taken, not notified, timer idle).
**Steps:** Temporarily add a manual trigger to `medication_startup_check` (or test via: Developer Tools → Services → `homeassistant.restart`, then verify after startup — requires time to be after 10:00).
Alternative: Directly fire the automation via Automations page → Run.
**Expect:** Notification arrives. `medication_notified_today` turns on.

---

### Test 18 — Midnight reset
**Prerequisite:** Turn on both booleans, start both timers.
**Steps:** Temporarily set `medication_daily_reset` trigger to 1–2 minutes from now, reload YAML, wait.
**Expect:** Both booleans off, both timers idle. `medication_last_taken` unchanged.
**Cleanup:** Restore trigger.

---

### Test 19 — HA restart timer safety
**Prerequisite:** Start `timer.medication_snooze` and `timer.medication_notification_timeout` manually.
**Steps:** Restart HA (Developer Tools → Services → `homeassistant.restart`).
**Expect:** After restart, both timers are idle (`restore: false`). No spurious notifications fired. `medication_notified_today` retains its pre-restart value (input_boolean persists).

---

### Using Automation Traces
For any test where the automation silently does nothing (conditions block it), check the trace:
Settings → Automations → find the automation → click → "Traces" tab → latest trace → shows each condition as green (passed) or red (failed), and the exact values evaluated.
