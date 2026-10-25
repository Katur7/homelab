# Summary: Spec 10 — Kids Bedroom Lights & Wake-up Automation

## Summary of Changes

Implemented Milestone 10 for the Kids' Bedroom:
1. **ZHA Light Group & Fallback**:
   - Outlined ZHA Zigbee group creation (`light.kids_bedroom_lights`) for multicast synchronisation across `light.ikea_kids1`, `light.ikea_kids2`, and `light.ikea_kids3`.
   - Added HA light group fallback (`light.kids_bedroom_bulbs`) directly inside the package.
2. **Shelly 1 Detached Mode & Protection**:
   - Provided guide for switching Shelly 1 Gen4 into Detached mode.
   - Fail-safe automation (`shelly_kids_keep_relay_powered`) guarantees `switch.shelly_1_kids` remains ON. If turned off while in default mode, it toggles the lights and restores continuous power.
   - Switch automation (`shelly_kids_wall_switch_toggle`) triggers light toggle on wall switch action.
3. **Master Automation Control**:
   - `input_boolean.kids_bedroom_automations`: UI toggle to pause/disable scheduled routines (e.g., during school holidays) without breaking physical wall switch operation.
4. **Morning Wake-Up Routine**:
   - Weekdays at 07:00, gently fades lights from 2% to 100% over 15 minutes.
   - Concurrently starts Music Assistant playlist 19 on `media_player.jukebox_jukebox` ramping volume from 5% (0.05) to 35% (0.35).
   - Interruptible: Automatically aborts if master toggle is turned off or if lights are manually turned off.

## Files Created
- [`services/home-assistant/specs/10-kids-bedroom-lights/plan.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/10-kids-bedroom-lights/plan.md)
- [`services/home-assistant/specs/10-kids-bedroom-lights/summary.md`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/10-kids-bedroom-lights/summary.md)
- [`services/home-assistant/config/packages/kids_bedroom.yaml`](file:///Users/grimur/personal-code/homelab/services/home-assistant/config/packages/kids_bedroom.yaml)
