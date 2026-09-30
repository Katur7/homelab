# Play Barnkanalen on Chromecast with Google TV — Spec 07 Plan

## Context
Provide an automated, one-touch way to turn on the TV and tune directly to **Barnkanalen (SVT Barn)** on a Chromecast with Google TV via Home Assistant using the native **Android TV Remote** integration (`remote.chromecast`).

---

## Architecture & How It Works

1. **Target Entity**: `remote.chromecast` (Android TV Remote integration).
2. **HDMI-CEC Power On**: Calling `remote.turn_on` wakes the Chromecast from standby, signaling the TV via HDMI-CEC to power on and switch to the Chromecast input.
3. **App Launch & Automated Navigation**:
   - Launches SVT Play (`https://www.svtplay.se`).
   - Waits 4 seconds for the "Vem tittar?" profile screen to render.
   - Sends `DPAD_DOWN` + `DPAD_CENTER` to select **"Titta utan profil"** (Watch without profile).
   - Waits 3 seconds for the Home screen to load.
   - Sends `DPAD_LEFT` to open the sidebar menu.
   - Moves down 4 times (`DPAD_DOWN`) to reach **"Kanaler"**.
   - Sends `DPAD_CENTER` to open the channels view.
   - Moves right 2 times (`DPAD_RIGHT`) to highlight **Barnkanalen**.
   - Sends `DPAD_CENTER` to start playback.

---

## Package Components

File: [barnkanalen.yaml](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/barnkanalen.yaml)

### Scripts
- `script.play_barnkanalen`:
  - Wakes up Chromecast / TV via HDMI-CEC.
  - Launches SVT Play.
  - Automates profile bypass and navigates to Barnkanalen.
- `script.turn_off_tv`:
  - Puts `remote.chromecast` into standby and turns off the TV via HDMI-CEC.

---

## Dashboard Card Example

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
