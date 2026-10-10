# HA-09: Water Leak Alarm — Specification & Plan

## Context
Water leaks can cause severe structural and financial damage within minutes. Home Assistant monitors water leak sensors, but without configured automations, leak events go unnoticed. Conversely, immediate unbuffered alerts trigger false alarms during physical sensor testing or battery changes.

This milestone establishes a 24/7 water leak monitoring and alerting package in Home Assistant. It includes a 15-second grace period to suppress false alarms during short testing, critical push alerts that bypass Do Not Disturb, 10-minute repeat reminders, a dashboard mute toggle, and automatic resolution notifications when sensors dry.

---

## Design Decisions

1. **Sensor Discovery & Dynamic Scope**:
   - Automatically monitors all `binary_sensor` entities where `device_class == 'moisture'`.
   - Exclusions are managed via `group.water_leak_exclusions` (defaulting to empty). Any sensor in this group is ignored.
   - Requires no hardcoding of entity IDs when new leak sensors are paired.

2. **Grace Period**:
   - Hardcoded in YAML at **15 seconds** before triggering an alert.
   - Quick tests (e.g., wetting contacts for 3–10 seconds and wiping dry) resolve silently without sending any notification.

3. **Notification Service & Urgency**:
   - Target: `notify.grimur_mobile_phones`.
   - **Critical Alert Configuration**:
     - Android: `priority: high`, `importance: max`, `ttl: 0`, `channel: "Water Leak Alerts"`, `color: "#D32F2F"`.
     - iOS: `push.sound.critical: 1`, `push.sound.volume: 1.0`.
     - Bypasses Do Not Disturb / phone silent mode.
   - Operating Hours: **24/7** (no quiet hours suppression).

4. **Alert Identification & Multi-Sensor Context**:
   - The notification identifies the specific sensor that triggered the alert.
   - If multiple sensors are active simultaneously, the message appends the names of all other currently wet sensors.

5. **Repeat Alerts & Silence/Mute Toggle**:
   - If water remains detected, notifications repeat every **10 minutes**.
   - An `input_boolean.water_leak_muted` toggle is provided on the Home Assistant dashboard to silence repeating alarms while dealing with the issue or away from home.
   - **Auto-Reset**: Once all monitored sensors return to dry (`sensor.active_water_leaks == 0`), the mute toggle automatically resets to `off` so future events are never inadvertently silenced.

6. **Recovery / Cleared Notification**:
   - When a wet sensor returns to dry and remains dry for **5 seconds** (debounce period against contact flutter / wiping), a normal-priority "Water leak cleared" push notification is sent.
   - Cleared notifications are only sent if the sensor was wet for at least 15 seconds (preventing test runs from triggering cleared notifications).

7. **Home Assistant Startup Resilience**:
   - If Home Assistant restarts while a leak is already active, an audit check triggers after 30 seconds of uptime and sends an alert if leaks are detected and unmuted.

---

## Files Created

| File | Purpose |
|---|---|
| [`services/home-assistant/config/packages/water_leak_alarm.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/water_leak_alarm.yaml) | Package containing helpers, template sensors, scripts, and automations |
| [`services/home-assistant/specs/09-water-leak-alarm/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/09-water-leak-alarm/plan.md) | Technical specification and design rationale |
| [`services/home-assistant/specs/09-water-leak-alarm/summary.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/09-water-leak-alarm/summary.md) | Milestone summary |

---

## Components

### 1. Helpers & Groups
- `input_boolean.water_leak_muted`: Dashboard mute toggle to silence repeating alerts.
- `input_datetime.water_leak_last_notified`: Tracks the timestamp of the last dispatched alert to enforce the 10-minute repeat interval.
- `group.water_leak_exclusions`: Entity group for leak detectors that should be excluded from monitoring.

### 2. Template Sensors
- `sensor.active_water_leaks`:
  - State: Integer count of unexcluded `binary_sensor` entities with `device_class: moisture` in `on` state.
  - Attributes: `devices` list of currently wet sensor friendly names.
  - Icon: `mdi:water-alert` when active, `mdi:water-check` when dry.

### 3. Scripts
- `script.water_leak_send_critical_notification`: Sends high-priority / critical push notification to `notify.grimur_mobile_phones`.
- `script.water_leak_send_cleared_notification`: Sends normal-priority push notification to `notify.grimur_mobile_phones`.

### 4. Automations
- `water_leak_alert_on_detection`: Triggers on state change to `on`, waits 15 seconds, verifies still `on`, dispatches critical alert, and stamps `water_leak_last_notified`.
- `water_leak_repeating_alert`: Evaluates every minute; if active leaks exist, mute is `off`, and $\ge 10$ minutes have elapsed since last notification, resends critical alert.
- `water_leak_alert_cleared`: Triggers on state change from `on` to `off` (where `on` lasted $\ge 14\text{s}$), waits 5-second debounce, verifies still `off`, sends cleared notification, and resets mute boolean if active leak count is zero.
- `water_leak_check_on_startup`: Runs 30 seconds after Home Assistant start to catch any leaks active across reboots.

---

## Lovelace Dashboard Card Example

```yaml
type: entities
title: 💧 Water Leak Monitor
show_header_toggle: false
entities:
  - entity: sensor.active_water_leaks
    name: Active Leaks
  - entity: input_boolean.water_leak_muted
    name: Silence Repeat Alerts
  - entity: input_datetime.water_leak_last_notified
    name: Last Alert Sent
```

---

## Verification & Testing

1. **Short Test (< 15 seconds)**:
   - Moisten the sensor probes for 5 seconds, then wipe dry.
   - Verify: No push notifications are received (neither alert nor cleared).
2. **Real / Extended Test (> 15 seconds)**:
   - Moisten the sensor probes and leave wet for 20 seconds.
   - Verify: Critical alert arrives on phone at $T \approx 15\text{s}$.
3. **Mute Functionality**:
   - While still wet, turn ON `input_boolean.water_leak_muted`.
   - Verify: 10-minute repeat notification is suppressed.
4. **Resolution & Auto-Reset**:
   - Dry the sensor thoroughly.
   - Verify: At $T \approx 5\text{s}$ after drying, a "Water leak cleared" notification arrives.
   - Verify: `input_boolean.water_leak_muted` automatically turns back OFF.
