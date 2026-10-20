/**
 * Shelly Plus 2PM mJS Script: Awning Wind Safety Monitor & Telemetry
 *
 * WIRING & DIRECTION MAPPING:
 *   - O1 (Cover.Open  / Up arrow ▲)   = Retract awning (roll UP)
 *   - O2 (Cover.Close / Down arrow ▼) = Extend awning  (roll DOWN)
 *
 * NOTE: Keep Shelly.emitEvent(...) calls within the first 5 KB of this file
 * so Home Assistant's Shelly integration automatically discovers the event types.
 */

var CONFIG = {
  DIGITAL_INPUT: "input:100",    // Add-on digital input component ID
  COVER_ID: 0,                  // Shelly Plus 2PM cover ID
  CHECK_INTERVAL_MS: 2000,      // Evaluation window (2 seconds)
  WIND_TRIGGER_PULSES: 10,      // X value: pulses per evaluation window to trigger
  SUSTAINED_WINDOWS: 1,         // Y time: consecutive windows over X required to trip/reset
  LOCKOUT_TIME_MS: 900000,      // 15 minutes of calm required to clear lockout
  BOOT_GRACE_MS: 60000,         // 60-second initial lockout on reboot
  DEBOUNCE_TIME_MS: 15,         // 15 ms minimum pulse interval (filters contact bounce)
  TELEMETRY_INTERVAL_MS: 10000  // 10 seconds check to report changed pulse counts
};

var state = {
  pulseCount: 0,
  lastPulseTime: 0,
  consecutiveWindWindows: 0,
  isLocked: true,
  lockoutTimerHandle: null,
  lastReportedPulses: 0,
  lastEmittedPulses: -1
};

// Emit events to Home Assistant via native Shelly RPC WebSocket.
// Literal event names MUST be passed directly to Shelly.emitEvent for HA discovery.
function publishLockout(pulses) {
  state.lastEmittedPulses = pulses;
  Shelly.emitEvent("wind_lockout", {
    locked: true,
    pulses: pulses
  });
}

function publishClear() {
  state.lastEmittedPulses = 0;
  Shelly.emitEvent("wind_clear", {
    locked: false,
    pulses: 0
  });
}

function publishTelemetry() {
  if (state.lastReportedPulses === state.lastEmittedPulses) {
    return;
  }
  state.lastEmittedPulses = state.lastReportedPulses;
  Shelly.emitEvent("wind_telemetry", {
    locked: state.isLocked,
    pulses: state.lastReportedPulses
  });
}

function triggerWindSafety(pulses) {
  print("WIND SAFETY TRIP! Pulses counted:", pulses);

  // 1. Immediately issue local cover retract command (Cover.Open = O1 = Up/Retract)
  Shelly.call("Cover.Open", { id: CONFIG.COVER_ID }, function (res, err) {
    if (err) {
      print("Error issuing Cover.Open (Retract):", JSON.stringify(err));
    } else {
      print("Cover.Open (Retract) issued successfully.");
    }
  });

  // 2. Set lockout state and notify Home Assistant
  state.isLocked = true;
  publishLockout(pulses);

  // 3. Clear any existing lockout expiration timer (sliding window reset)
  if (state.lockoutTimerHandle !== null) {
    Timer.clear(state.lockoutTimerHandle);
    state.lockoutTimerHandle = null;
    print("Lockout timer reset (sliding window refreshed for 15 minutes of calm).");
  }

  // 4. Start fresh 15-minute calm countdown
  state.lockoutTimerHandle = Timer.set(CONFIG.LOCKOUT_TIME_MS, false, function () {
    state.isLocked = false;
    state.lockoutTimerHandle = null;
    publishClear();
    print("Wind safety lockout expired: 15 minutes of calm achieved. Awning unlocked.");
  });
}

function getNowMs() {
  if (typeof Shelly.getUptimeMs === "function") {
    return Shelly.getUptimeMs();
  }
  if (typeof Date !== "undefined" && typeof Date.now === "function") {
    return Date.now();
  }
  return 0;
}

// ==========================================
// EVENT HANDLER: REED SWITCH PULSE ACCUMULATOR
// ==========================================
Shelly.addEventHandler(function (event) {
  if (event.component === CONFIG.DIGITAL_INPUT && event.info && event.info.state === true) {
    var nowMs = getNowMs();
    if (nowMs === 0 || nowMs - state.lastPulseTime >= CONFIG.DEBOUNCE_TIME_MS) {
      state.pulseCount++;
      state.lastPulseTime = nowMs;
    }
  }
});

// ==========================================
// PERIODIC EVALUATION WINDOW (Every 2 seconds)
// ==========================================
Timer.set(CONFIG.CHECK_INTERVAL_MS, true, function () {
  var pulses = state.pulseCount;
  state.pulseCount = 0;
  state.lastReportedPulses = pulses;

  if (pulses >= CONFIG.WIND_TRIGGER_PULSES) {
    state.consecutiveWindWindows++;
    if (state.consecutiveWindWindows >= CONFIG.SUSTAINED_WINDOWS) {
      triggerWindSafety(pulses);
    }
  } else {
    state.consecutiveWindWindows = 0;
  }
});

// ==========================================
// TELEMETRY TIMER (Every 10s, only emits when pulse count changes)
// ==========================================
Timer.set(CONFIG.TELEMETRY_INTERVAL_MS, true, function () {
  publishTelemetry();
});

// ==========================================
// BOOT INITIALIZATION & GRACE PERIOD
// ==========================================
print("Awning Wind Safety Monitor initializing...");
state.isLocked = true;
publishLockout(0);

state.lockoutTimerHandle = Timer.set(CONFIG.BOOT_GRACE_MS, false, function () {
  state.isLocked = false;
  state.lockoutTimerHandle = null;
  publishClear();
  print("Boot grace period expired. Ambient baseline established, awning unlocked.");
});
