# Play Barnkanalen on Chromecast — Spec 07 Plan

## Context
Provide an instant, one-touch way to turn on the TV and stream **Barnkanalen (SVT Barn)** directly to a Chromecast with Google TV via Home Assistant using the native **Google Cast** integration (`media_player.living_room_tv_2`).

---

## Architecture & How It Works

1. **Target Entity**: `media_player.living_room_tv_2` (Google Cast integration).
2. **HDMI-CEC Power On**: Calling `media_player.turn_on` wakes the Chromecast from standby, signaling the TV via HDMI-CEC to power on and switch to the Chromecast input.
3. **Direct Live Stream Playback**:
   - Calling `media_player.play_media` instructs Google Cast's Default Media Receiver to stream Barnkanalen directly using the verified SVT DASH manifest:
     - **URL**: `https://ed7.cdn.svt.se/l6/se/svtb/manifest.mpd?format=dash&defaultSubLang=1`
     - **Type**: `video/mp4`
   - Bypasses all app launches, account logins, menus, and profile prompts.

---

## Package Components

File: [barnkanalen.yaml](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/barnkanalen.yaml)

### Scripts
- `script.play_barnkanalen`:
  - Wakes up Chromecast / TV via HDMI-CEC if off or in standby.
  - Streams Barnkanalen directly via `media_player.play_media` on `media_player.living_room_tv_2`.
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
