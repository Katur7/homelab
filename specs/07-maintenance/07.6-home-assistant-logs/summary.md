# Milestone 07.6 Summary: Home Assistant Log Audit

**Date:** 2026-03-30
**Status:** `COMPLETE — no config changes required`

---

## Log Sources Reviewed

- `home-assistant.log` (current boot, 2026-03-29)
- `home-assistant.log.1` (previous boot, 2026-03-25 → 2026-03-29)

---

## Findings

### ✅ No action — Expected startup behaviour

| Warning | Verdict |
|---------|---------|
| `[homeassistant.bootstrap]` Waiting for integrations: tuya, switch_as_x, openuv, smhi, tomorrowio, google_translate, shelly, shopping_list | All completed within ~60s of the second warning. Tuya is a cloud auth integration and blocks switch_as_x (which wraps Tuya devices). No third warning = all resolved. Not a failure. |
| `[homeassistant.components.openuv]` Skipping update due to missing data: from_time | Race condition on startup — OpenUV runs before the `sun` component has computed sunrise/sunset. Self-resolves. Appears on every boot. Not actionable. |
| `[py.warnings]` SyntaxWarning in `rich/segment.py` | Third-party library issue, Python 3.14 compatibility. Not actionable — will resolve in a future HA/rich update. |
| `[aioesphomeapi]` einkframe @ 192.168.86.177 | Single event 2026-03-28. Device was briefly offline. Did not recur. |

### ⚠️ Hardware — action required outside HA config

| Issue | Device | Action |
|-------|--------|--------|
| Repeated Zigbee delivery failures (5 occurrences, 3 days) | IKEA BADRING Water Leakage Sensor (ieee=d4:48:67:ff:fe:5a:b1:9a) | Check battery and Zigbee range. Sensor may be offline. |
| ZCL Time cluster delivery errors every ~4h on 2026-03-27; automation "Failed to send request" on 2026-03-28 and 2026-03-29 | Aqara dimmer master bedroom (0x6F09 / lumi.switch.agl011) | Intermittent Zigbee signal loss. Errors ceased after 2026-03-27 — monitor. If recurring, add a Zigbee router device nearby. |

### ✅ No action — automation already correct

| Warning | Verdict |
|---------|---------|
| `automation.master_bedroom_light_remotes` "Already running" | Automation is already set to `mode: single`. This warning is the expected log message when the mode discards a duplicate trigger. Correct behaviour. |

---

## No Config File Changes Made

All HA config files (automations, configuration.yaml, etc.) are gitignored.
No compose changes were required for this milestone.

## No Architecture / global.env Changes Required
