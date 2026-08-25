let eventSequence = 0;

const makeEvent = (type, severity, message, source, timestamp) => ({
  id: `${type}-${timestamp}-${eventSequence += 1}`,
  type,
  severity,
  message,
  source,
  timestamp,
  acknowledged: false,
});

export function deriveRealtimeEvents(previous, next, receivedAt = new Date().toISOString()) {
  const timestamp = receivedAt;
  const events = [];

  if (next.emergency.panic && !previous?.emergency.panic) {
    events.push(makeEvent("panic", "critical", "PATIENT PANIC ALERT — WARD 01", "Ward 01", timestamp));
  }
  if (!next.emergency.panic && previous?.emergency.panic) {
    events.push(makeEvent("panic-resolved", "healthy", "Patient panic alert resolved — Ward 01", "Ward 01", timestamp));
  }
  if (next.bed.vibration && !previous?.bed.vibration) {
    events.push(makeEvent("vibration", "warning", "Bed vibration detected in Ward 01", "hospital_ward_01", timestamp));
  }
  if (next.rfid.lastUid && next.rfid.lastUid !== previous?.rfid.lastUid) {
    events.push(makeEvent("rfid", "info", `RFID scanned: ${next.rfid.lastUid}`, "RC522 · Ward 01", timestamp));
  }
  if (previous && next.connectivity.mqtt !== previous.connectivity.mqtt) {
    const connected = next.connectivity.mqtt;
    events.push(makeEvent("mqtt", connected ? "healthy" : "critical", connected ? "MQTT transport reconnected" : "MQTT transport disconnected", "hospital_ward_01", timestamp));
  }

  return events;
}

export function reconnectDelay(attempt) {
  return Math.min(30000, 1000 * (2 ** Math.min(Math.max(attempt - 1, 0), 5)));
}
