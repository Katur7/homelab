# Summary — Spec 05: Evening Medication Reminder

## What Changed
- Extended `services/home-assistant/config/packages/medication_reminder.yaml` to track both morning and evening medications.
- Renamed morning datetime entity to `input_datetime.medication_morning_last_taken` and added `input_datetime.medication_evening_last_taken`.
- Added dedicated evening helpers: `input_boolean.medication_evening_notified_today`, `timer.medication_evening_snooze`, and `timer.medication_evening_notification_timeout`.
- Consolidated scripts and automations:
  - `script.medication_mark_taken` parameterised by `period: morning | evening`.
  - `script.medication_send_reminder` parameterised by `period: morning | evening` with dynamic action lists.
  - Unified trigger handlers for timers, scheduled checks, fallbacks, and mobile notification actions.
- Routed the shared NFC tag (`medication_nfc_scanned`) using a 20:00 cutoff: scans before 20:00 log morning medication; scans at or after 20:00 log evening medication.
- Added evening automations: 22:00 initial reminder, snooze timer handling, notification actions ("Taken", "Snooze 30m"), 23:30 final cutoff, hourly timeout re-prompting, and HA startup check.
- Updated midnight reset to clear all morning and evening timers and booleans.

## Why
User takes an evening medication in addition to morning medication. Both use the same physical NFC tag on the medicine box, but require separate entity logging so both can be independently tracked and inspected in Home Assistant.

## Key Design Decisions
- **Shared NFC tag with 20:00 cutoff**: No second physical tag required.
- **Consolidated scripts/automations**: Parameterized architecture (following `HA-03`) avoids duplicating the entire reminder pipeline, keeping the package concise and maintainable.
- **Independent timers and booleans**: Prevents timing races or state leakage between morning and evening reminder chains.
- **Separate notification tags**: `medication_morning_reminder` and `medication_evening_reminder` prevent notifications from replacing or overwriting each other in the notification shade.
- **Backward compatibility**: Preserved handlers for legacy morning notification action strings (`MEDICATION_TAKEN`, `MEDICATION_SNOOZE_30`, `MEDICATION_REMIND_HOME`).

## New Secrets
None required (reuses existing `medication_nfc_tag_id`, `phone_device_id`, and `phone_notify_service`).

## Architecture/global.env Updates Needed?
No.
