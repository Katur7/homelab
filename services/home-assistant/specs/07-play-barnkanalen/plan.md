# Play Barnkanalen on Chromecast with Google TV — Spec 07 Plan

## Context
Provide a reliable, one-touch way to turn on the TV and tune directly to the **Barnkanalen (SVT Barn)** live stream in Home Assistant using the native **Android TV Remote** integration (`remote.chromecast`).

---

## Architecture & How It Works

1. **Target Entity**: `remote.chromecast` (Android TV Remote integration).
2. **HDMI-CEC Power On**: Calling `remote.turn_on` wakes the Chromecast from standby, signaling the TV via HDMI-CEC to power on and switch to the Chromecast input.
3. **App Launch & Profile Bypass**:
   - Calling `remote.turn_on` with `activity: "https://www.svtplay.se/kanaler/svtbarn"` launches the SVT Play app.
   - SVT Play presents a "Vem tittar?" (Who is watching?) profile selection prompt.
   - The script waits 3 seconds, sends `DPAD_DOWN` to highlight **"Titta utan profil"** (Watch without profile), and sends `DPAD_CENTER` to select it.
   - After a 2-second pause to let SVT Play load into guest mode, the script re-issues the `https://www.svtplay.se/kanaler/svtbarn` deep link, immediately starting playback of the Barnkanalen channel.

---

## Package Components

File: [barnkanalen.yaml](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/barnkanalen.yaml)

### Scripts
- `script.play_barnkanalen`:
  - Wakes up Chromecast / TV via HDMI-CEC if off or in standby.
  - Launches SVT Play.
  - Selects "Titta utan profil" via D-pad commands (`DPAD_DOWN` -> `DPAD_CENTER`).
  - Tunes into the live Barnkanalen stream.
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
