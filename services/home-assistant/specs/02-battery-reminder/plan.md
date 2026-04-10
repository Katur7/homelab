# Battery Reminder — Home Assistant Automation Plan

## Context
Monitor all HA-connected devices that expose a `battery` device class sensor (primarily Zigbee devices via ZHA). Send a push notification to the user's phone when any device's battery drops at or below a configurable threshold. Notifications are suppressed between 23:00–08:05 (quiet hours). A daily morning check at 08:05 catches devices that were already low before the automation was deployed or during quiet hours. Notifications are consolidated into a single message per check. A device is silenced until its battery recovers above the threshold (battery replaced), at which point it re-arms automatically.

---

## Step 0 — Discovery: List All Battery Devices (Run First)

Before writing any YAML, run this template in **Developer Tools → Template** to see every battery sensor HA already knows about, sorted by level:

```jinja2
{% set sensors = states.sensor
    | selectattr('attributes.device_class', 'eq', 'battery')
    | selectattr('state', 'is_number')
    | sort(attribute='state') | list %}
{% if sensors | count == 0 %}
  No battery sensors found.
{% else %}
  Found {{ sensors | count }} battery sensor(s):
  {% for s in sensors %}
  - {{ s.name }}: {{ s.state | int }}%  [{{ s.entity_id }}]
  {% endfor %}
{% endif %}
```

> Note: `sort(attribute='state')` on string states produces lexicographic ordering (e.g. `"9"` sorts after `"80"`). This is acceptable for discovery purposes. The automations and card avoid this by using explicit `float` comparisons in loops.

This confirms which entities will be monitored and validates that ZHA is reporting numeric battery levels. Review the output before proceeding — if any device shows `unavailable` or a string like `"low"`, note it for the implementation notes below.

---

## Files to Create

| File | Purpose |
|---|---|
| `/config/packages/battery_reminder.yaml` | All helpers, scripts, automations |
| Lovelace dashboard card | Added to an existing dashboard view via the UI editor |

Requires the packages include directive in `/config/configuration.yaml` (already added by milestone 01):
```yaml
homeassistant:
  packages: !include_dir_named packages/
```

---

## Helpers

```yaml
input_number:
  battery_low_threshold:
    name: "Battery Low Threshold (%)"
    min: 5
    max: 50
    step: 5
    initial: 20
    unit_of_measurement: "%"
    icon: mdi:battery-alert

group:
  battery_monitor_exclusions:
    name: "Battery Monitor Exclusions"
    entities:
      - sensor.pixel_7_battery_level
      - sensor.pixel_7a_battery_level
```

To add or remove excluded devices, edit the group's `entities` list and run `Developer Tools → YAML → Reload Groups`. No HA restart required.

No per-device tracking helpers needed. The threshold crossing (state going from above to at/below) acts as the trigger guard — HA fires the automation once per crossing, suppressing repeats until the battery recovers and drops again.

---

## Template Sensor

Exposes the count and names of all currently-low devices. Used by the Lovelace card and useful for conditional dashboard badges.

```yaml
template:
  - sensor:
      - name: "Devices with Low Battery"
        unique_id: battery_low_device_count
        state: >
          {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
          {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
          {% set ns = namespace(count=0) %}
          {% for s in states.sensor
              | selectattr('attributes.device_class', 'eq', 'battery')
              | selectattr('state', 'is_number') %}
            {% if s.state | float <= threshold and s.entity_id not in excluded %}
              {% set ns.count = ns.count + 1 %}
            {% endif %}
          {% endfor %}
          {{ ns.count }}
        attributes:
          devices: >
            {# Both devices and levels use the same zero-pad sort so their indices stay in sync #}
            {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
            {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
            {% set ns = namespace(keyed=[]) %}
            {% for s in states.sensor
                | selectattr('attributes.device_class', 'eq', 'battery')
                | selectattr('state', 'is_number') %}
              {% if s.state | float <= threshold and s.entity_id not in excluded %}
                {% set ns.keyed = ns.keyed + ["%03d" | format(s.state | int) ~ "||" ~ s.name] %}
              {% endif %}
            {% endfor %}
            {% set ns2 = namespace(items=[]) %}
            {% for entry in ns.keyed | sort %}
              {% set ns2.items = ns2.items + [entry.split("||")[1]] %}
            {% endfor %}
            {{ ns2.items }}
          levels: >
            {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
            {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
            {% set ns = namespace(keyed=[]) %}
            {% for s in states.sensor
                | selectattr('attributes.device_class', 'eq', 'battery')
                | selectattr('state', 'is_number') %}
              {% if s.state | float <= threshold and s.entity_id not in excluded %}
                {% set ns.keyed = ns.keyed + ["%03d" | format(s.state | int)] %}
              {% endif %}
            {% endfor %}
            {{ ns.keyed | sort | map('int') | list }}
        unit_of_measurement: "devices"
        icon: >
          {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
          {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
          {% set ns = namespace(found=false) %}
          {% for s in states.sensor
              | selectattr('attributes.device_class', 'eq', 'battery')
              | selectattr('state', 'is_number') %}
            {% if s.state | float <= threshold and s.entity_id not in excluded %}{% set ns.found = true %}{% endif %}
          {% endfor %}
          {{ 'mdi:battery-alert' if ns.found else 'mdi:battery-check' }}
```

---

## Scripts

### `script.battery_send_notification`
Builds and sends a consolidated push notification to the same phone as milestone 01.

```yaml
script:
  battery_send_notification:
    alias: "Battery: Send Notification"
    fields:
      device_list:
        description: "List of formatted strings: '<Name> (<level>%)'"
        selector:
          object:
    sequence:
      - service: notify.grimur_mobile_phones
        data:
          title: "Low Battery"
          message: >
            {{ device_list | join('\n') }}
```

---

## Automations

### 1. `battery_low_on_change`
Fires in real-time when any entity's battery crosses the threshold downward. Uses an `event: state_changed` trigger so the entity list is fully dynamic — new ZHA devices are covered immediately with no reload required.

```yaml
automation:
  - alias: "Battery: Alert on Level Drop"
    id: battery_low_on_change
    trigger:
      - platform: event
        event_type: state_changed
    condition:
      - condition: template
        value_template: >
          {{ trigger.event.data.get('new_state') is not none
             and trigger.event.data.new_state.attributes.get('device_class') == 'battery'
             and trigger.event.data.new_state.state not in ['unavailable', 'unknown']
             and trigger.event.data.new_state.state | float(-1)
                <= states('input_number.battery_low_threshold') | float(20)
             and (trigger.event.data.old_state is none
                  or trigger.event.data.old_state.state | float(100)
                     > states('input_number.battery_low_threshold') | float(20))
             and trigger.event.data.new_state.entity_id
                not in (state_attr('group.battery_monitor_exclusions', 'entity_id') | default([])) }}
      - condition: time
        after: "08:05:00"
        before: "23:00:00"
    action:
      - service: script.battery_send_notification
        data:
          device_list:
            - "{{ trigger.event.data.new_state.name }} ({{ trigger.event.data.new_state.state | int }}%)"
```

> **Event trigger note:** This fires on every `state_changed` event across all of HA. The first condition acts as a cheap filter — HA evaluates the `device_class` check before anything else. On a typical home instance this is negligible. No automation reload is ever needed; newly paired ZHA devices are covered the moment their first state is reported.

### 2. `battery_daily_check`
Runs at 08:05, just after the quiet-hours window ends. Catches devices already low at startup and any that dropped overnight during quiet hours. The 5-minute offset avoids a race with real-time automation 1, which uses `after: "08:05:00"`.

```yaml
  - alias: "Battery: Daily Morning Check"
    id: battery_daily_check
    trigger:
      - platform: time
        at: "08:05:00"
    condition:
      - condition: template
        value_template: >
          {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
          {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
          {% set ns = namespace(found=false) %}
          {% for s in states.sensor
              | selectattr('attributes.device_class', 'eq', 'battery')
              | selectattr('state', 'is_number') %}
            {% if s.state | float <= threshold and s.entity_id not in excluded %}
              {% set ns.found = true %}
            {% endif %}
          {% endfor %}
          {{ ns.found }}
    action:
      - service: script.battery_send_notification
        data:
          device_list: >
            {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
            {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
            {% set ns = namespace(keyed=[]) %}
            {% for s in states.sensor
                | selectattr('attributes.device_class', 'eq', 'battery')
                | selectattr('state', 'is_number') %}
              {% if s.state | float <= threshold and s.entity_id not in excluded %}
                {# Zero-pad level so alphabetic sort == numeric sort (e.g. "009" < "080") #}
                {% set ns.keyed = ns.keyed + ["%03d" | format(s.state | int) ~ "||" ~ s.name ~ " (" ~ s.state | int ~ "%)"] %}
              {% endif %}
            {% endfor %}
            {% set ns2 = namespace(items=[]) %}
            {% for entry in ns.keyed | sort %}
              {% set ns2.items = ns2.items + [entry.split("||")[1]] %}
            {% endfor %}
            {{ ns2.items }}
```

> The `variables` block is intentionally absent. Storing a list of State objects in an automation variable is unreliable — HA serialises the rendered result, which does not preserve `.name`/`.state` attributes for later iteration. Building the list inline in the action template is the correct approach.

---

## Lovelace Card

Add as a new card to any dashboard view. Shows a live sorted table of all battery devices with a colour-coded indicator. Works with stock HA, no custom components required.

```yaml
type: markdown
title: Battery Levels
content: >
  {% set threshold = states('input_number.battery_low_threshold') | float(20) %}
  {% set excluded = state_attr('group.battery_monitor_exclusions', 'entity_id') | default([]) %}
  {% set sensors = states.sensor
      | selectattr('attributes.device_class', 'eq', 'battery')
      | selectattr('state', 'is_number')
      | rejectattr('entity_id', 'in', excluded)
      | list %}
  {% if sensors | count == 0 %}
  _No battery sensors found._
  {% else %}
  | Device | Level |
  |--------|-------|
  {# Zero-pad level as sort key so 9% sorts before 10%, not after 80% #}
  {% set ns = namespace(keyed=[]) %}
  {% for s in sensors %}
    {% set ns.keyed = ns.keyed + ["%03d" | format(s.state | int) ~ "||" ~ s.name ~ "||" ~ s.state] %}
  {% endfor %}
  {% for entry in ns.keyed | sort %}
  {% set parts = entry.split("||") %}
  {% set level = parts[2] | float %}
  {% if level <= threshold %}
  | ⚠️ {{ parts[1] }} | **{{ level | int }}%** |
  {% elif level <= 40 %}
  | 🟡 {{ parts[1] }} | {{ level | int }}% |
  {% else %}
  | ✅ {{ parts[1] }} | {{ level | int }}% |
  {% endif %}
  {% endfor %}
  {% endif %}
```

> The card uses a zero-padded key sort (`"%03d" | format(level)`) so numeric ordering is correct: `9%` sorts before `10%`, not after `80%`. Level comparisons use `| float` to handle any sensor that reports decimals.
>
> **Note:** The card lists all battery devices, not just low ones. With many ZHA devices this table can grow long. If it becomes unwieldy, a second "low only" view can be added by wrapping the `{% for %}` in `{% if level <= threshold %}` only.

---

## Key Design Decisions
- **Step 0 first:** Running the discovery template before writing YAML confirms ZHA is reporting numeric values and reveals the exact entity IDs.
- **`event: state_changed` trigger (Option A):** Automation 1 listens to all state changes and filters in the condition. Fully dynamic — no entity list to maintain, no reload needed. New ZHA devices are covered from their first state report. Automation 3 (daily reload) is not needed and has been removed.
- **08:05 as daily check time:** 5 minutes after quiet hours end. Reduces (but does not fully eliminate) the chance of a double notification — a device crossing the threshold at the exact second the daily check fires would appear in both. Acceptable: the window is one second wide and the result is an extra notification, not a missed one.
- **No per-device tracking helpers:** Threshold crossing suppresses duplicates naturally; battery replacement re-arms the device automatically.
- **Consolidated daily / single-device real-time:** Daily check lists all low devices in one notification; real-time alert is specific so the user immediately knows which device to address.
- **Quiet hours 23:00–08:05:** Real-time crossing alert is suppressed. The daily 08:05 check acts as the deferred delivery for any drops that occurred overnight.
- **Known gap — drop and recover during quiet hours:** If a device drops below threshold then recovers above it between 23:00–08:05 (e.g. a glitching Zigbee sensor that briefly reports a low value), no notification is ever sent. For real battery drain this is irrelevant. For flapping sensors it means a spurious low reading is silently dropped, which is actually desirable behaviour.
- **ZHA numeric battery:** ZHA reports battery as a numeric percentage for all mainstream Zigbee devices. The `is_number` filter handles any edge-case device that does not.
- **Float comparison throughout:** All numeric threshold comparisons use `| float` casts and `<=` (inclusive) so a device at exactly the threshold value is treated as low — consistent across real-time alert, daily check, template sensor, and card.
- **Exclusion group (`group.battery_monitor_exclusions`):** Phone battery sensors (companion app) are excluded via a YAML `group`. The group's `entity_id` attribute is a list; all template blocks check `s.entity_id not in excluded` with a `| default([])` guard in case the group is unavailable at startup. To add/remove devices: edit the group in the package file and run `Reload Groups` — no restart needed.
- **`"||"` sort key separator:** The zero-pad sort uses `"||"` as a delimiter. If a device's friendly name contains `"||"` (e.g. `"Front Door || Porch"`), the name will be truncated in notifications and the card. Avoid `"||"` in device names in ZHA/HA.
- **Card 40% "medium" tier is static:** The 🟡 tier triggers at `level <= 40` regardless of the configured threshold. If threshold is raised above 40%, the 🟡 tier disappears (all low devices show ⚠️). If threshold is lowered to 5%, devices between 6–40% show 🟡 even though they are well above the alert threshold. The 40% boundary is a cosmetic display aid only, not tied to notification logic.

---

## Test Plan

### Tools used
- **Developer Tools → Template** — validate Jinja before deploying
- **Developer Tools → States** — inspect and manually override battery sensor states
- **Developer Tools → Services** — call scripts directly
- **Automations page → Traces** — inspect condition pass/fail

---

### Test 0 — Discovery template
**Steps:** Paste the Step 0 template into Developer Tools → Template.
**Expect:** All ZHA battery devices listed with numeric levels. No `unavailable` entries (or note which ones are).

---

### ✅ Test 1 — Helpers loaded correctly
**Steps:** After reloading YAML (`Developer Tools → YAML → Reload All`), open States, search "battery".
**Expect:** `input_number.battery_low_threshold` at value 20, `sensor.devices_with_low_battery` visible.

---

### ✅ Test 2 — Template sensor counts correctly
**Steps:** States tab → find any battery sensor → override state to `10`.
**Expect:** `sensor.devices_with_low_battery` state = 1 (or increments). Device name appears in `devices` attribute.
**Cleanup:** ZHA battery sensors only report on the device's own schedule (typically every 1–4 hours). The States tab override will persist until the next real ZHA report — this does not affect other tests, which use their own sensor overrides.

---

### Test 3 — New ZHA device covered immediately
**Prerequisite:** Pair a new ZHA device that has a battery sensor.
**Steps:** After pairing, set its battery sensor state below threshold via the States tab.
**Expect:** Real-time notification fires without any `automation.reload`. Confirm that the notification body shows the device's **friendly name** (not its entity ID). If the entity ID appears instead, `trigger.event.data.new_state.name` is not resolving correctly for this HA version — fall back to `trigger.event.data.new_state.attributes.get('friendly_name', trigger.event.data.new_state.entity_id)`.

---

### Test 4 — Lovelace card renders
**Steps:** Add the chosen card to a dashboard view, open the view.
**Expect:** All battery devices listed with levels. The overridden sensor from Test 2 shows with ⚠️ / bold text.

---

### ✅ Test 5 — Notification script works
**Steps:** Developer Tools → Services → call `script.battery_send_notification`:
```yaml
device_list:
  - "Test Remote (12%)"
  - "Front Door Sensor (8%)"
```
**Expect:** Push notification arrives on phone titled "Low Battery" with both lines in the body.

---

### Test 6 — Daily check fires and lists low devices
**Prerequisite:** At least one battery sensor below threshold (override via States tab).
**Steps:** Temporarily set `battery_daily_check` trigger time to 1–2 minutes from now (in quiet-hours-safe window), reload YAML, wait.
**Expect:** Notification arrives listing the low device(s), sorted by level ascending.
**Cleanup:** Restore trigger to `08:05:00`, reload YAML.

---

### Test 7 — Daily check silent when all batteries healthy
**Prerequisite:** Ensure no battery sensor is below threshold.
**Steps:** Trigger `battery_daily_check` as in Test 6.
**Expect:** No notification. Trace shows the count condition failed (count = 0).

---

### ✅ Test 8 — Real-time alert on threshold crossing (business hours)
**Prerequisite:** Battery sensor currently above threshold. Time is between 08:05–23:00.
**Steps:** States tab → set the sensor state to a value below threshold (e.g. `15`).
**Expect:** Push notification within seconds naming the specific device and level.

---

### ✅ Test 9 — Dead battery (0%) triggers alert
**Prerequisite:** Battery sensor currently above threshold. Time is between 08:05–23:00.
**Steps:** States tab → set the sensor state to `0`.
**Expect:** Push notification fires naming the device at `0%`. Confirms the former `> 0` guard is gone. Also check the daily check: temporarily trigger `battery_daily_check` and verify the 0% device appears in the notification list.

---

### Test 10 — Real-time alert suppressed during quiet hours
**Prerequisite:** Battery sensor above threshold.
**Steps:** Temporarily set quiet hours condition to cover now (e.g. `after: "00:00:00"` `before: "23:59:00"`), reload, then override the sensor state below threshold.
**Expect:** No notification. Trace shows time condition failed.
**Cleanup:** Restore original time condition, reload YAML.

---

### ✅ Test 11 — Real-time alert suppressed for already-low device
**Prerequisite:** Battery sensor already below threshold (from Test 8).
**Steps:** Set the same sensor state to one value lower (e.g. `14`).
**Expect:** No notification. Trace shows the `from_state > threshold` condition failed.

---

### ✅ Test 12 — Device re-arms after battery replaced
**Prerequisite:** Battery sensor at `15` (below threshold).
**Steps:** Set state to `80` (new battery), then set back to `15`.
**Expect:** Notification fires on the second state change. Fresh crossing after recovery re-arms correctly.

---

### ✅ Test 13 — Excluded devices are silenced
**Prerequisite:** `sensor.pixel_7_battery_level` or `sensor.pixel_7a_battery_level` in the group (default).
**Steps:**
1. States tab → set `sensor.pixel_7_battery_level` to `10` (below threshold).
2. Wait a few seconds.
**Expect:** No notification. Automation trace shows condition failed on the exclusion check. `sensor.devices_with_low_battery` count does NOT increment. Lovelace card does NOT list the phone sensor.
**Cleanup:** Set the phone sensor back to its real state.

---

### Test 14 — Threshold change takes effect immediately
**Steps:**
1. Set `input_number.battery_low_threshold` to `30` in the UI.
2. Find a battery sensor at `25` (above 20, below 30).
**Expect:** `sensor.devices_with_low_battery` increments without any YAML reload. Lovelace card shows the device with ⚠️.
