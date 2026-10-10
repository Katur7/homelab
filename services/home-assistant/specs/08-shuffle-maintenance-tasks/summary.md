# HA-08: Maintenance Task Shuffle — Summary

## What Changed
Added `script.maintenance_shuffle_overdue` to [`services/home-assistant/config/packages/maintenance_reminder.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/maintenance_reminder.yaml).

## Why
When multiple recurring maintenance tasks fall overdue at the same time, daily reminders can create friction and procrastination. Shuffling overdue tasks across the next two weeks with an initial 2-day grace period gives a fresh start and breaks up task clusters so only one chore appears at a time.

## How It Works
- Checks interval-based tasks (`ac_filter`, `plant_office`, `bike_tyre`, `bike_chain`) against their last-done and snooze timestamps.
- Shuffles overdue tasks using Jinja's `| shuffle` filter.
- Assigns each task to an evenly spaced date between Day 2 and Day 14.
- Updates `input_datetime.maintenance_<task_id>_snooze_until` to `00:00:00` on the assigned date.
- Dismisses any active notifications for those tasks on mobile devices (`clear_notification`).
- Creates a `persistent_notification` in the Home Assistant UI with the new schedule breakdown.
