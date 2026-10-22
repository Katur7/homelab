/**
 * Shelly Plus 2PM mJS Script: Awning Wind Sensor Telemetry (Passive Mode)
 *
 * Passive telemetry-only mode:
 *   - Counts reed switch pulses on input:100 with 15 ms software debounce.
 *   - Emits pulse count updates to Home Assistant via Shelly.emitEvent() when values change.
 *   - Does NOT issue any Cover.Open / Cover.Close commands (no relay switching).
 *
 * NOTE: Keep Shelly.emitEvent(...) calls within the first 5 KB of this file
 * so Home Assistant's Shelly integration automatically discovers the event types.
 */

var CONFIG = {
  DIGITAL_INPUT: "input:100",    // Add-on digital input component ID
  CHECK_INTERVAL_MS: 2000,      // Evaluation window (2 seconds)
  WIND_TRIGGER_PULSES: 10,      // Reference threshold for logging/status
  LOCKOUT_TIME_MS: 900000,      // 15 minutes
  DEBOUNCE_TIME_MS: 15,         // 15 ms minimum pulse interval (filters contact bounce)
  TELEMETRY_INTERVAL_MS: 10000  // 10 seconds check to report changed pulse counts
};

var state = {
  pulseCount: 0,
  lastPulseTime: 0,
  isLocked: false,
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

function recordHighWind(pulses) {
  print("High wind threshold reached (passive mode, no cover action). Pulses:", pulses);

  state.isLocked = true;
  publishLockout(pulses);

  if (state.lockoutTimerHandle !== null) {
    Timer.clear(state.lockoutTimerHandle);
    state.lockoutTimerHandle = null;
  }

  state.lockoutTimerHandle = Timer.set(CONFIG.LOCKOUT_TIME_MS, false, function () {
    state.isLocked = false;
    state.lockoutTimerHandle = null;
    publishClear();
    print("High wind indicator cleared after 15 minutes of calm.");
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
    recordHighWind(pulses);
  }
});

// ==========================================
// TELEMETRY TIMER (Every 10s, only emits when pulse count changes)
// ==========================================
Timer.set(CONFIG.TELEMETRY_INTERVAL_MS, true, function () {
  publishTelemetry();
});

// ==========================================
// INITIALIZATION
// ==========================================
print("Awning Wind Sensor Telemetry started (passive mode - no cover control).");
publishClear();
