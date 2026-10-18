# Technical Specification & Commissioning Guide: Awning Controller

**Device:** Shelly Plus 2PM (Gen2) + Shelly Plus Add-on  
**Sensors:** Somfy Soliris Combination Sun & Wind Sensor (3-wire passive)  
**Switch:** Schneider Exxact Jalusibrytare (momentary spring-return)  
**Downstream:** External Relay Box controlling tubular awning motors (20s travel time)  
**Package:** `services/home-assistant/config/packages/awning_controller.yaml`  
**Shelly Script:** `services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js`  

---

## 1. System Overview & Architecture

This solution integrates a Somfy Soliris combination sensor and an existing external motor relay box into Home Assistant via a **Shelly Plus 2PM** and **Shelly Plus Add-on**.

```
       +------------------------------------+
       |       Schneider Exxact Switch      |
       |  L: Phase | ▲: Up (S1) | ▼: Dn (S2)| (Momentary Spring)
       +------------------+-----------------+
                          | 230V
+-------------------------v----------------------------+
|                  Shelly Plus 2PM                     |
|  Profile: Cover (Time-based limits: 22s Open/Close)  |
|  Inputs: S1 (Up/Retract), S2 (Down/Extend)           |
|  Outputs: O1 -> External Box Up, O2 -> Ext Box Down  |
|                                                      |
|  [Local mJS: shelly-wind-safety.js]                  |
|    - 15 ms debounced pulse counter on input:100      |
|    - Instant local Cover.Close upon wind threshold   |
|    - Sliding 15-minute calm lockout                  |
|    - Emits RPC events (Shelly.emitEvent) every 10s   |
+-------------------------+----------------------------+
                          | Internal Bus
+-------------------------v----------------------------+
|                Shelly Plus Add-on                    |
|  GND: Somfy Common (C)                               |
|  Analog In + Vref+R1 Out jumper: Somfy Sun wire      |
|  Digital In: Somfy Wind wire (Reed pulse to GND)     |
+------------------------------------------------------+
```

---

## 2. Step-by-Step Shelly Device Configuration

Perform these steps in the Shelly web interface (`http://<shelly-ip>`):

### Step A: Change Device Profile to 'Cover'
1. Go to **Settings** $\rightarrow$ **Device Profile**.
2. Select **Cover** (Roller Shutter) mode.
3. Save and let the device reboot.

### Step B: Configure Cover Parameters & Travel Durations (22s)
Because the Shelly drives external relay coils rather than the motor windings directly, automatic power-based calibration cannot detect motor stall current drops. Use **timed duration limits**:
1. Go to **Cover Settings** $\rightarrow$ **Safety / Obstacle Detection**:
   * Turn **Obstacle Detection OFF** (Disabled).
2. Go to **Cover Settings** $\rightarrow$ **Movement Time Limits**:
   * Set **Open Time Limit (`maxtime_open`)**: **`22` seconds** (20s physical travel + 2s safety buffer).
   * Set **Close Time Limit (`maxtime_close`)**: **`22` seconds** (20s physical travel + 2s safety buffer).
   * The safety buffer ensures the outside box's motor internal limit switches disconnect power completely before the Shelly relay opens.
3. In **Input Mode**:
   * Set inputs to **Dual Button** (configured for momentary push-buttons with spring return).
   * Verify Button 1 triggers Retract (Up) and Button 2 triggers Extend (Down). If inverted, toggle the **Reverse Directions** setting.

### Step C: Enable Add-on Peripherals
1. Go to **Add-on** settings in the Shelly Web UI.
2. **Digital Input**:
   * Add a new peripheral $\rightarrow$ **Digital Input**.
   * Name: `Somfy Wind Sensor`
   * This registers as `input:100`.
3. **Analog Input**:
   * Add a new peripheral $\rightarrow$ **Analog Input**.
   * Name: `Somfy Sun Sensor`
   * Unit: Set to **Percent (%)** (or Volts).
   * This registers as `input:101` / `volts:100`.

---

## 3. Local mJS Wind Safety Script Deployment

Because standard Gen2 Plus devices (`Shelly Plus 2PM`) do not support Gen3 Virtual Components, the script communicates with Home Assistant natively using **`Shelly.emitEvent()`** over the existing Shelly integration WebSocket connection.

1. In the Shelly Web UI, go to **Scripts**.
2. Click **Add Script**, name it `wind_safety`.
3. Paste the updated contents of [`shelly-wind-safety.js`](file:///Users/grimur/personal-code/homelab/services/home-assistant/specs/06-awning-controller/shelly-wind-safety.js).
4. Click **Save**.
5. Enable **Run on boot** (toggle switch).
6. Click **Start**.
7. In the script console output at the bottom of the page, verify the initial boot logs:
   ```text
   Awning Wind Safety Monitor initializing...
   Boot grace period expired. Ambient baseline established, awning unlocked.
   ```

---

## 4. Home Assistant Configuration & Entity Mapping

### Step D: Enable the Script Event Entity in Home Assistant
Once `wind_safety` is saved and running on the Shelly:
1. In Home Assistant, go to **Settings** $\rightarrow$ **Devices & Services** $\rightarrow$ **Shelly**.
2. Find your Awning Shelly device, click the **`...`** menu, and select **Reload** *(this makes Home Assistant scan the script and discover `Shelly.emitEvent`)*.
3. Open the Shelly device page in Home Assistant.
4. Look under **Events** (click "+1 disabled entity" if hidden) for the script event entity (e.g. `event.<shelly_name>_wind_safety`).
5. Click the entity $\rightarrow$ click the **Gear icon (Settings)**:
   * Toggle **Enabled** to **ON**.
   * Set the **Entity ID** to: **`event.awning_wind_safety`**
   * Click **Update** (wait 30 seconds for HA to reload the entity).

### Expected Entity IDs in Home Assistant

| Function | Entity ID in HA | Source |
|---|---|---|
| Awning Cover | `cover.outdoor_shelly_markiser_awning` | Shelly Cover channel |
| Sun Sensor | `sensor.outdoor_shelly_markiser_awning_somfy_sun_sensor_analogue` | Shelly Add-on Analog In (%) |
| Script Event Stream | `event.awning_wind_safety` | Shelly Script (`Shelly.emitEvent`) |
| Wind Lockout | `binary_sensor.awning_wind_lockout` | Auto-created by `awning_controller.yaml` template |
| Wind Pulses | `sensor.awning_wind_pulses` | Auto-created by `awning_controller.yaml` template |
| Raw Wind Input | `binary_sensor.outdoor_shelly_markiser_awning_somfy_wind_sensor` | Shelly Add-on Digital In (`input:100`) — *can be disabled in HA to prevent high-wind DB spam* |

### Package: `packages/awning_controller.yaml`
The package provides:
- **Template Entities**: Automatically converts `event.awning_wind_safety` attributes (`locked` and `pulses`) into `binary_sensor.awning_wind_lockout` and `sensor.awning_wind_pulses`.
- **`input_boolean.awning_automation_enabled`**: Master enable/disable toggle for comfort automations.
- **`input_boolean.awning_manual_override`**: Engaged if the user manually retracts the awning on a sunny day. Resets at midnight or when manually reopened.
- **`input_number.awning_sun_threshold_extend`** (default 65%): Sunlight level required to auto-extend.
- **`input_number.awning_sun_threshold_retract`** (default 35%): Sunlight level below which awning auto-retracts.
- **`input_datetime.awning_active_start`** (default 08:30) & **`input_datetime.awning_active_end`** (default 18:00): Allowed daytime operating window.

---

## 5. Commissioning & Verification Checklist

- [ ] **Wall Switch Verification**:
  - Press Up: Motor retracts until limit switch.
  - Press Down: Motor extends until limit switch.
- [ ] **Shelly Web UI Cover Test**:
  - Test Open and Close buttons in the Shelly UI. Confirm 22s `maxtime_open` and `maxtime_close` allow full 20s travel before relay shuts off.
- [ ] **Anemometer Spin Test**:
  - While awning is extended, spin the Somfy Soliris anemometer wheel by hand.
  - Observe `sensor.awning_wind_pulses` updating in Home Assistant.
  - Spin briskly to reach $\ge 10$ pulses in a 2-second window.
  - **Verify immediate retraction**: Shelly issues `Cover.Close` and `binary_sensor.awning_wind_lockout` switches to `on` in Home Assistant.
- [ ] **Sliding Lockout Test**:
  - Spin the anemometer again at minute 5: verify script logs indicate sliding lockout timer refresh.
  - Allow 15 uninterrupted minutes of calm: verify lockout clears and switches to `off`.
- [ ] **Sunlight Threshold Tuning**:
  - Check `sensor.awning_sun_sensor` during midday sun and cloudy conditions.
  - Adjust `input_number.awning_sun_threshold_extend` and `input_number.awning_sun_threshold_retract` on the Home Assistant dashboard to fit your local orientation.
