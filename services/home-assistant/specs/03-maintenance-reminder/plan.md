# HA-03: Maintenance Reminder System

## Tasks

| task_id         | task_name                | interval | type     |
|-----------------|--------------------------|----------|----------|
| `ac_filter`     | Clean AC filters         | 14 days  | interval |
| `plant_office`  | Water office plant       | 7 days   | interval |
| `bike_tyre`     | Check bike tyre pressure | 30 days  | interval |
| `bike_chain`    | Lube bike chain          | 30 days  | interval |
| `water_line`    | Empty outside water line | Oct 1    | calendar |

## Key Design Decisions

**Generic system** — one shared `maintenance_send_reminder` script parameterised by `task_id` + `task_name`. Action handlers pattern-match on action string prefix (`MAINTENANCE_DONE_*` etc.) and extract `task_id` via template. Adding a task = 2 helpers + 7 lines in the daily check.

**Per-task helpers** — `input_datetime.maintenance_<task_id>_last_done` and `_snooze_until`, initialised to `2000-01-01`. Overdue check: days since last_done ≥ interval AND now > snooze_until.

**Reminder time** — `input_datetime.maintenance_reminder_time` (time-only helper, default 16:00). Used as `at:` target in time triggers.

**Notification actions** — Done / Snooze 1 day / Snooze 1 week. No action = remind tomorrow naturally via next day's cron (no timer needed).

**`water_line`** — separate automation, triggers Oct 1 at reminder time. Done check is year-scoped (`last_done.year != now.year`).

## File
`services/home-assistant/config/packages/maintenance_reminder.yaml`

## Rollback
Delete the package file and restart HA.
