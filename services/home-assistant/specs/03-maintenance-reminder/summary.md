# HA-03: Maintenance Reminder System — Summary

## What Changed
Added a Home Assistant package (`services/home-assistant/config/packages/maintenance_reminder.yaml`) implementing a generic maintenance reminder system with mobile push notifications.

## Why
Recurring maintenance tasks (AC filters, plant watering, bike maintenance, winterizing water line) were easy to forget. A notification-based system with snooze/done actions removes the need to track these manually.

## How It Works
- **Daily check automation** fires at a configurable time (`input_datetime.maintenance_reminder_time`, default 16:00).
- Each task has `_last_done` and `_snooze_until` `input_datetime` helpers.
- Overdue = days since last_done >= interval AND now > snooze_until.
- Notifications offer three actions: Done, Snooze 1 day, Snooze 1 week.
- `water_line` has a separate automation scoped to Oct 1 annually (year-based done check).

## Tasks

| task_id        | task_name                          | interval |
|----------------|------------------------------------|----------|
| ac_filter      | Clean AC filters                   | 14 days  |
| plant_office   | Water office plant                 | 7 days   |
| bike_tyre      | Check bike tyre pressure           | 30 days  |
| bike_chain     | Lube bike chain                    | 30 days  |
| water_line     | Empty outside water line before frost | Oct 1  |

## New Secrets
- `phone_notify_service` — must exist in `secrets.yaml` (notify service call, e.g. `notify.mobile_app_phone`).

## Architecture/global.env Updates
None required.
