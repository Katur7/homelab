# Play Barnkanalen on Chromecast — Spec 07 Plan

## Context
Provide an automated, self-healing way to turn on the TV and stream **Barnkanalen (SVT Barn)** directly to a Chromecast via Home Assistant using the **SVT Play** custom component (`svt_play`) and the **Google Cast** integration (`media_player.living_room_tv_2`).

---

## Architecture & How It Works

1. **Target Entity**: `media_player.living_room_tv_2` (Google Cast integration).
2. **HDMI-CEC Power On**: Calling `media_player.turn_on` wakes the Chromecast from standby, signaling the TV via HDMI-CEC to power on and switch to the Chromecast input.
3. **Dynamic URL Resolution & Playback**:
   - Calling `svt_play.play_channel` with `channel: barnkanalen` queries SVT Play's backend API (`api.svt.se`) on demand to fetch the active, authorized stream manifest URL.
   - Forwards that fresh URL to `media_player.living_room_tv_2` using the Cast receiver.
   - Never breaks when SVT updates CDN nodes, manifest paths, or streaming endpoints.

---

## Prerequisites

- **HACS Component**: `lindell/home-assistant-svt-play` installed.
- **Enabled in `configuration.yaml`**: `svt_play:`

---

## Package Components

File: [barnkanalen.yaml](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/barnkanalen.yaml)

### Scripts
- `script.play_barnkanalen`:
  - Wakes up Chromecast / TV via HDMI-CEC if off or in standby.
  - Calls `svt_play.play_channel` targeting `media_player.living_room_tv_2`.
- `script.turn_off_tv`:
  - Puts `media_player.living_room_tv_2` into standby and turns off the TV via HDMI-CEC.

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
