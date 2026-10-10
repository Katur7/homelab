# HA-08: Maintenance Task Shuffle

## Context
When recurring maintenance tasks are postponed, overdue tasks accumulate (e.g., multiple monthly chores due on the same day). Receiving daily reminders for several pending tasks at once leads to decision fatigue, task aversion, and continuous procrastination.

This milestone introduces a shuffle script that redistributes all currently overdue interval tasks across the next two weeks with an initial grace period, providing a fresh start without losing completion history.

---

## Design Decisions

1. **Eligible Tasks**:
   - Only recurring interval-based tasks (`ac_filter`, `plant_office`, `bike_tyre`, `bike_chain`) are evaluated.
   - Calendar/annual tasks (`water_line`) and tasks not currently overdue are ignored.

2. **Window & Grace Period**:
   - **Total Window**: 14 days.
   - **Initial Grace Period**: 2 days (48 hours of silence before the first shuffled task surfaces).
   - **Active Spacing Range**: Days 2 through 14.

3. **Randomization & Spacing**:
   - Overdue tasks are shuffled randomly using Home Assistant's `shuffle` filter.
   - The shuffled tasks are evenly spaced across the active range:
     - For $N = 1$: Scheduled at `now() + 2 days`.
     - For $N > 1$: Task index $i \in [0, N-1]$ is scheduled at:
       $$\text{offset\_days} = 2 + \operatorname{round}\left(i \times \frac{12}{N - 1}\right)$$
     - Examples:
       - 1 task: Day 2
       - 2 tasks: Day 2, Day 14
       - 3 tasks: Day 2, Day 8, Day 14
       - 4 tasks: Day 2, Day 6, Day 10, Day 14

4. **Snooze Mechanism**:
   - Modifies `input_datetime.maintenance_<task_id>_snooze_until` to `00:00:00` on the target slot date.
   - Preserves `maintenance_<task_id>_last_done` so historical records remain accurate.

5. **Notification Clearing & UI Feedback**:
   - Calls `clear_notification` on `!secret phone_notify_service` for each shuffled task tag (`maintenance_<task_id>`) to immediately remove active clutter from mobile devices.
   - Posts a `persistent_notification` in the Home Assistant UI detailing the scheduled tasks and their new due dates (or notifying if no tasks were overdue).
   - Sends no intrusive push notifications upon running.

6. **Trigger**:
   - Exposed as `script.maintenance_shuffle_overdue`, callable from Home Assistant dashboard cards and scripts.

---

## Files

- Specification: [`services/home-assistant/specs/08-shuffle-maintenance-tasks/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/08-shuffle-maintenance-tasks/plan.md)
- Implementation: [`services/home-assistant/config/packages/maintenance_reminder.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/maintenance_reminder.yaml)

---

## Dashboard Card Example

```yaml
type: button
name: Shuffle Overdue Tasks
icon: mdi:shuffle-variant
tap_action:
  action: call-service
  service: script.maintenance_shuffle_overdue
```

---

## Rollback
Remove `script.maintenance_shuffle_overdue` from `maintenance_reminder.yaml` and reload scripts or restart Home Assistant.
