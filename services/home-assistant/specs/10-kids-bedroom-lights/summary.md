# Summary: Spec 10 — Kids Bedroom Lights & Wake-up Automation

## Summary of Changes

Implemented Milestone 10 for the Kids' Bedroom:
1. **ZHA Light Group**:
   - Native ZHA Zigbee group (`light.kids_bedroom_lights`) for multicast synchronisation across `light.ikea_kids1`, `light.ikea_kids2`, and `light.ikea_kids3`.
2. **Shelly 1 Detached Mode & Direct Binding**:
   - Configured Shelly 1 Gen4 in Detached mode and direct-bound its `OnOff` client cluster to the ZHA Light Group for offline local control.
   - Added custom ZHA quirk (`services/home-assistant/config/zha_quirks/shelly_1_gen4.py`) for `("Shelly", "1")` so ZHA exposes the detached `Input` as a standard `binary_sensor` under **Sensors** on the Shelly Zigbee device card.
   - Added `shelly_kids_out_of_sync_toggle` automation so flipping the wall switch always toggles the lights even if the lights were previously changed from Home Assistant.
3. **Master Automation Control**:
   - `input_boolean.kids_bedroom_automations`: UI toggle to pause/disable scheduled routines (e.g., during school holidays) without breaking physical wall switch operation.
4. **Morning Wake-Up Routine**:
   - Weekdays at 07:00, gently fades lights from 2% to 100% over 15 minutes.
   - Concurrently starts Music Assistant playlist 19 on `media_player.jukebox_jukebox` ramping volume from 5% (0.05) to 35% (0.35).
   - Interruptible: Automatically aborts if master toggle is turned off or if lights are manually turned off.

## Files Created / Modified
- [`services/home-assistant/specs/10-kids-bedroom-lights/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/10-kids-bedroom-lights/plan.md)
- [`services/home-assistant/specs/10-kids-bedroom-lights/summary.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/10-kids-bedroom-lights/summary.md)
- [`services/home-assistant/config/packages/kids_bedroom.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/kids_bedroom.yaml)
- [`services/home-assistant/config/zha_quirks/shelly_1_gen4.py`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/zha_quirks/shelly_1_gen4.py)
- [`services/home-assistant/config/configuration.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/configuration.yaml)
