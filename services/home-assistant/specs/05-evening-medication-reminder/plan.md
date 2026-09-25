# Evening Medication Reminder & Shared NFC Tag Routing — Spec 05 Plan

## Context
Extend the medication reminder system (`services/home-assistant/config/packages/medication_reminder.yaml`) to support an evening medication taken around 22:00, in addition to the existing morning medication.
Both medications share the same physical NFC tag on the medicine box, but route to separate entities based on a 20:00 time cutoff.

---

## Key Design Decisions

1. **Shared NFC Tag Routing:**
   - Single tag ID: `!secret medication_nfc_tag_id` with `!secret phone_device_id` guard.
   - **Time cutoff at 20:00:**
     - Scan before 20:00: marks morning medication taken (`script.medication_mark_taken` with `period: morning`).
     - Scan at or after 20:00: marks evening medication taken (`script.medication_mark_taken` with `period: evening`).

2. **Entity Renaming & Symmetry:**
   - Morning entity renamed from `input_datetime.medication_last_taken` to `input_datetime.medication_morning_last_taken`.
   - New evening entity created: `input_datetime.medication_evening_last_taken`.
   - Distinct helpers for snooze, timeout, and notification state to ensure complete isolation.

3. **Consolidated Architecture (Patterned after HA-03):**
   - Single parameterized `script.medication_mark_taken` accepting `period: morning | evening`.
   - Single parameterized `script.medication_send_reminder` accepting `period: morning | evening`, dynamically rendering title, tags, and action buttons.
   - Unified notification action handlers and timer completion listeners that dynamically detect `period`.

4. **Evening Schedule & Actions:**
   - **Trigger:** 22:00 fixed cron if evening medication not taken today.
   - **Notification Actions:** Simplified to "Taken" (`MEDICATION_EVENING_TAKEN`) and "Snooze 30m" (`MEDICATION_EVENING_SNOOZE_30`).
   - **Snooze:** 30-minute timer (`timer.medication_evening_snooze`).
   - **Dismissal Timeout:** 1-hour nudge (`timer.medication_evening_notification_timeout`) re-prompting until cutoff.
   - **Hard Cutoff:** 23:30 (`medication_hard_fallback`) cancels active timers and sends a final notification with only the "Taken" button.
   - **Startup Check:** HA restart between 22:00 and 23:30 triggers a reminder if not yet notified.

5. **Midnight Reset:**
   - At 00:00, cancels all 4 timers and turns off all 3 boolean flags.
   - Datetime entities retain their timestamp; the template date check `[:10] != now().strftime('%Y-%m-%d')` cleanly resets the logic for the next day.

6. **Backward Compatibility:**
   - Notification action triggers accept both `MEDICATION_MORNING_*` and legacy `MEDICATION_*` action strings.

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

- `script.medication_mark_taken`: parameterised script (`period: morning | evening`) setting datetime, cancelling timers, clearing notification.
- `script.medication_send_reminder`: parameterised script (`period: morning | evening`, `message`, `include_home_action`, `final_reminder`).
- `script.medication_reset_test_state`: resets both datetimes to `2000-01-01` and clears all booleans and timers.

---

## Automations (Consolidated: 12 total)

1. `medication_morning_off_charger`: off-charger morning trigger starts 30-min snooze.
2. `medication_timer_done`: handles snooze timer completion for both morning and evening.
3. `medication_scheduled_reminder`: handles 10:00 (morning) and 22:00 (evening) crons.
4. `medication_nfc_scanned`: routes scan event by `< 20:00:00` (morning) vs `>= 20:00:00` (evening).
5. `medication_action_taken`: handles `MEDICATION_*_TAKEN` notification actions.
6. `medication_action_snooze`: handles `MEDICATION_*_SNOOZE_30` notification actions.
7. `medication_morning_action_home`: handles morning `MEDICATION_MORNING_REMIND_HOME` action.
8. `medication_morning_arrived_home`: handles morning presence arrival.
9. `medication_hard_fallback`: handles 17:00 (morning) and 23:30 (evening) hard cutoffs.
10. `medication_notification_timeout`: handles dismissal timeouts for both periods.
11. `medication_startup_check`: restart checks for both morning and evening windows.
12. `medication_daily_reset`: midnight reset at 00:00.

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
3. **Evening 22:00 Trigger**: Trigger `medication_scheduled_reminder` with `id: evening` → push notification arrives with "Taken" and "Snooze 30m".
4. **Evening Snooze Action**: Fire event `mobile_app_notification_action` with `action: MEDICATION_EVENING_SNOOZE_30` → `timer.medication_evening_snooze` starts for 30m.
5. **Evening Taken Action**: Fire event `mobile_app_notification_action` with `action: MEDICATION_EVENING_TAKEN` → `medication_evening_last_taken` updates to now, timers clear.
6. **Evening 23:30 Fallback**: Trigger `medication_hard_fallback` with `id: evening` → cancels active timers, notification arrives with only "Taken" action.
7. **Midnight Reset**: Trigger `medication_daily_reset` → cancels all 4 timers, turns off all 3 booleans.
