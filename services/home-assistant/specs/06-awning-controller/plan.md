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
The package currently provides:
- **Template Entities**: Automatically converts `event.awning_wind_safety` attributes (`locked` and `pulses`) into `binary_sensor.awning_wind_lockout` and `sensor.awning_wind_pulses`.
- **Sunset Auto-Retract**: Retracts (`cover.open_cover`) the awning 30 minutes after sunset if it is extended (`closed`).

---

## 5. Implementation Roadmap & To-Do List

### Phase 1: Hardware & Sensor Verification
- [ ] **Fix 3-wire sensor wiring:** Identify Common, Sun, and Wind wires on the Somfy cable and connect them correctly to the Shelly Add-on (`GND`, `Analog In + Vref/R1`, `Digital In`).
- [ ] **Verify Add-on Digital In settings:** Ensure `input:100` in the Shelly UI is set to detached/no actions so reed pulses do not click the relays.
- [ ] **Confirm clean sensor readings:**
  - Sun sensor varies smoothly with ambient light (low at night, high in midday sun) instead of jumping between 66.8% and 17.7%.
  - Wind sensor registers pulses only on `input:100` / `sensor.awning_wind_pulses`.

### Phase 2: Threshold Calibration
- [ ] **Calibrate wind threshold:** Spin test and observe pulse counts during real breeze to determine the pulse threshold $X$ for safety retraction (e.g., 10 pulses / 2s).
- [ ] **Calibrate sun thresholds:** Note the percentage readings on overcast days vs. full direct sun to determine realistic extend (e.g., 65%) and retract (e.g., 35%) thresholds.

### Phase 3: Wind Safety & Local Script (Offline Protection)
- [ ] **Re-enable local retraction in `shelly-wind-safety.js`:** Restore `Cover.Open` (Up/Retract) upon threshold breach so wind safety functions 100% offline without depending on Wi-Fi or HA.
- [ ] **High wind sliding lockout:** Verify the 15-minute calm window resets on recurring gusts and signals `binary_sensor.awning_wind_lockout`.

### Phase 4: Comfort Automations & Override Logic
- [x] **Sunset auto-retract:** Retract 30m after sunset if extended *(implemented in `awning_controller.yaml`)*.
- [ ] **Auto-extend when sunny:** Deploy after sustained sun exposure ($\ge 10\text{ min}$) within active daytime operating hours.
- [ ] **Low-light auto-retract:** Retract if sun drops below threshold for $\ge 20\text{ min}$ during the day.
- [ ] **Manual override handling:** If manually rolled up via wall switch on a sunny day, prevent auto-extending until midnight or manual reopening.
- [ ] **Master automation toggle:** An `input_boolean.awning_automation_enabled` helper on the dashboard to pause sun automations while keeping wind safety active.

### Phase 5: Dashboard & Monitoring
- [ ] **Dashboard card:** A Lovelace card displaying awning position, sun %, wind pulses, lockout state, and threshold sliders.
- [ ] **Watchdog notification:** Alert via Home Assistant if the Shelly goes offline or the sensor becomes unavailable.

