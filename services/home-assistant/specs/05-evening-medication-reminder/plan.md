# Evening Medication Reminder & Shared NFC Tag Routing — Spec 05 Plan

## Context
Extend the medication reminder system (`services/home-assistant/config/packages/medication_reminder.yaml`) to support an evening medication taken around 22:00, in addition to the existing morning medication.
Both medications share the same physical NFC tag on the medicine box, but route to separate entities based on a 20:00 time cutoff.

---

## Key Design Decisions

1. **Shared NFC Tag Routing:**
   - Single tag ID: `!secret medication_nfc_tag_id` with `!secret phone_device_id` guard.
   - **Time cutoff at 20:00:**
     - Scan before 20:00: marks morning medication taken (`script.medication_morning_mark_taken`).
     - Scan at or after 20:00: marks evening medication taken (`script.medication_evening_mark_taken`).

2. **Entity Renaming & Symmetry:**
   - Morning entity renamed from `input_datetime.medication_last_taken` to `input_datetime.medication_morning_last_taken`.
   - New evening entity created: `input_datetime.medication_evening_last_taken`.
   - Distinct helpers for snooze, timeout, and notification state to ensure complete isolation.

3. **Evening Schedule & Actions:**
   - **Trigger:** 22:00 fixed cron if evening medication not taken today.
   - **Notification Actions:** Simplified to "Taken" (`MEDICATION_EVENING_TAKEN`) and "Snooze 30m" (`MEDICATION_EVENING_SNOOZE_30`).
   - **Snooze:** 30-minute timer (`timer.medication_evening_snooze`).
   - **Dismissal Timeout:** 1-hour nudge (`timer.medication_evening_notification_timeout`) re-prompting until cutoff.
   - **Hard Cutoff:** 23:30 (`medication_evening_2330_fallback`) cancels active timers and sends a final notification with only the "Taken" button.
   - **Startup Check:** HA restart between 22:00 and 23:30 triggers a reminder if not yet notified.

4. **Midnight Reset:**
   - At 00:00, cancels all 4 timers (morning + evening snooze and timeouts) and turns off all 3 boolean flags.
   - Datetime entities retain their timestamp; the template date check `[:10] != now().strftime('%Y-%m-%d')` cleanly resets the logic for the next day.

5. **Backward Compatibility:**
   - Morning notification action triggers accept both `MEDICATION_MORNING_*` and legacy `MEDICATION_*` action strings.

---

## File Modified
- `services/home-assistant/config/packages/medication_reminder.yaml`

---

## Entities

### `input_datetime`
- `medication_morning_last_taken` (renamed from `medication_last_taken`)
- `medication_evening_last_taken` (new)

### `input_boolean`
- `medication_morning_notified_today`
- `medication_morning_waiting_for_home`
- `medication_evening_notified_today` (new)

### `timer`
- `medication_morning_snooze` (30m)
- `medication_morning_notification_timeout` (1h)
- `medication_evening_snooze` (30m, new)
- `medication_evening_notification_timeout` (1h, new)

---

## Scripts

- `script.medication_morning_mark_taken`: sets morning datetime, cancels morning timers, clears waiting flag, dismisses morning notification.
- `script.medication_evening_mark_taken`: sets evening datetime, cancels evening timers, dismisses evening notification.
- `script.medication_morning_send_reminder`: sends push notification with tag `medication_morning_reminder`.
- `script.medication_evening_send_reminder`: sends push notification with tag `medication_evening_reminder`.
- `script.medication_reset_test_state`: resets both datetimes to `2000-01-01` and clears all booleans and timers.

---

## Automations

### NFC Tag Routing
- `medication_nfc_scanned`: routes scan event by `< 20:00:00` (morning) vs `>= 20:00:00` (evening).

### Morning Automations (Preserved & Namespaced)
- `medication_morning_off_charger`
- `medication_morning_timer_done`
- `medication_morning_10am`
- `medication_morning_action_taken`
- `medication_morning_action_snooze`
- `medication_morning_action_home`
- `medication_morning_arrived_home`
- `medication_morning_17_fallback`
- `medication_morning_notification_timeout`
- `medication_morning_startup_check`

### Evening Automations (New)
- `medication_evening_22pm`
- `medication_evening_timer_done`
- `medication_evening_action_taken`
- `medication_evening_action_snooze`
- `medication_evening_2330_fallback`
- `medication_evening_notification_timeout`
- `medication_evening_startup_check`

### Daily Reset
- `medication_daily_reset` (resets morning and evening timers and booleans at 00:00).

---

## Test Plan

### Setup
Call `script.medication_reset_test_state` via **Developer Tools → Actions**.

### Inspection Template
Paste into **Developer Tools → Template**:
```jinja
morning_taken_today:   {{ states('input_datetime.medication_morning_last_taken')[:10] == now().strftime('%Y-%m-%d') }}
morning_last_taken:    {{ states('input_datetime.medication_morning_last_taken') }}
morning_notified:      {{ states('input_boolean.medication_morning_notified_today') }}
morning_waiting_home:  {{ states('input_boolean.medication_morning_waiting_for_home') }}
morning_snooze:        {{ states('timer.medication_morning_snooze') }}
morning_timeout:       {{ states('timer.medication_morning_notification_timeout') }}

evening_taken_today:   {{ states('input_datetime.medication_evening_last_taken')[:10] == now().strftime('%Y-%m-%d') }}
evening_last_taken:    {{ states('input_datetime.medication_evening_last_taken') }}
evening_notified:      {{ states('input_boolean.medication_evening_notified_today') }}
evening_snooze:        {{ states('timer.medication_evening_snooze') }}
evening_timeout:       {{ states('timer.medication_evening_notification_timeout') }}
```

### Verification Steps
1. **NFC Scan < 20:00**: Fire `tag_scanned` with registered phone `device_id` before 20:00 → only `medication_morning_last_taken` is updated.
2. **NFC Scan >= 20:00**: Fire `tag_scanned` at or after 20:00 → only `medication_evening_last_taken` is updated.
3. **Evening 22:00 Trigger**: Trigger `medication_evening_22pm` → push notification arrives with "Taken" and "Snooze 30m".
4. **Evening Snooze Action**: Fire event `mobile_app_notification_action` with `action: MEDICATION_EVENING_SNOOZE_30` → `timer.medication_evening_snooze` starts for 30m.
5. **Evening Taken Action**: Fire event `mobile_app_notification_action` with `action: MEDICATION_EVENING_TAKEN` → `medication_evening_last_taken` updates to now, timers clear.
6. **Evening 23:30 Fallback**: Trigger `medication_evening_2330_fallback` → cancels active timers, notification arrives with only "Taken" action.
7. **Midnight Reset**: Trigger `medication_daily_reset` → cancels all 4 timers, turns off all 3 booleans.

