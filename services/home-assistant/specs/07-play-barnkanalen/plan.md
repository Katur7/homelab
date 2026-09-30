# Play Barnkanalen on Chromecast with Google TV — Spec 07 Plan

## Context
Provide a reliable, one-touch way to turn on the TV and tune directly to the **Barnkanalen (SVT Barn)** live stream in Home Assistant using the native **Android TV Remote** integration with entity `remote.chromecast`.

---

## Architecture & How It Works

1. **Target Entity**: `remote.chromecast` (Android TV Remote integration).
2. **HDMI-CEC Power On**: Calling `remote.turn_on` wakes the Chromecast from standby, signaling the TV via HDMI-CEC to power on and switch to the Chromecast input.
3. **App Deep Linking**: Calling `remote.open_url` with `https://www.svtplay.se/kanaler/svtbarn` opens the live channel directly in the installed **SVT Play** app (`se.svt.svtplay`).

---

## Prerequisites

- **SVT Play App**: Installed from the Google Play Store on the Chromecast with Google TV.
- **HDMI-CEC**: Enabled on TV to allow waking the screen via the Chromecast.

---

## Package Components

File: [barnkanalen.yaml](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/barnkanalen.yaml)

### Scripts
- `script.play_barnkanalen`:
  - Checks if `remote.chromecast` is `off` or `standby`; if so, turns it on and waits 2 seconds for wakeup and HDMI handshake.
  - Calls `remote.open_url` with `https://www.svtplay.se/kanaler/svtbarn` to launch SVT Play straight into Barnkanalen.
- `script.turn_off_tv`:
  - Calls `remote.turn_off` on `remote.chromecast` to return to standby and trigger TV power-off via HDMI-CEC.

---

## Dashboard Card Examples

### Standard Button Card
```yaml
type: button
name: Barnkanalen
icon: mdi:television-play
tap_action:
  action: call-service
  service: script.play_barnkanalen
hold_action:
  action: call-service
  service: script.turn_off_tv
```

### Tile Card
```yaml
type: tile
entity: script.play_barnkanalen
name: Barnkanalen
icon: mdi:television-play
tap_action:
  action: call-service
  service: script.play_barnkanalen
```

---

## Trigger Integration Examples

### Physical Button (e.g., Zigbee / IKEA Tradfri / Aqara)
```yaml
alias: "Kids Button - Play Barnkanalen"
trigger:
  - platform: event
    event_type: zha_event
    event_data:
      device_ieee: "xx:xx:xx:xx:xx:xx:xx:xx"
      command: "press"
action:
  - action: script.play_barnkanalen
```

### Scheduled Routine
```yaml
alias: "Morning Routine - Barnkanalen"
trigger:
  - platform: time
    at: "06:45:00"
condition:
  - condition: time
    weekday:
      - mon
      - tue
      - wed
      - thu
      - fri
action:
  - action: script.play_barnkanalen
```
