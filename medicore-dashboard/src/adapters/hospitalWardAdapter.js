const WARD_DEVICE_ID = "hospital_ward_01";

const hasNumber = value => typeof value === "number" && Number.isFinite(value);
const normalizeTimestamp = value => {
  if (!value) return new Date().toISOString();
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed.toISOString();
  const match = String(value).match(/^(\d{2})-(\d{2})-(\d{4})\s+(\d{1,2})\.(\d{2})\.(\d{2})\s+(AM|PM)$/i);
  if (!match) return new Date().toISOString();
  const [, day, month, year, rawHour, minute, second, meridiem] = match;
  let hour = Number(rawHour) % 12;
  if (meridiem.toUpperCase() === "PM") hour += 12;
  return new Date(Number(year), Number(month) - 1, Number(day), hour, Number(minute), Number(second)).toISOString();
};
const reading = (moduleOnline, value, unit = "", unavailable = "Sensor Offline") => ({
  available: Boolean(moduleOnline && hasNumber(value)),
  value: moduleOnline && hasNumber(value) ? value : null,
  display: moduleOnline && hasNumber(value) ? `${value}${unit}` : unavailable,
});

export function extractHospitalWard(envelope, deviceId = WARD_DEVICE_ID) {
  if (!envelope) return null;
  const root = envelope.data?.nodes ? envelope.data : envelope;
  const node = root.nodes?.[deviceId];
  if (node?.data) return {
    ...node.data,
    device_id: node.device_id || deviceId,
    node_type: node.node_type || "smart_hospital_ward",
    _online: node.online,
    _connectionStatus: node.connection_status,
    _ageSeconds: node.age_seconds,
    _receivedAt: node.last_seen || root.timestamp || envelope.timestamp,
  };
  if (envelope.device?.data) return {
    ...envelope.device.data,
    device_id: envelope.device.device_id || deviceId,
    node_type: envelope.device.node_type || "smart_hospital_ward",
    _online: envelope.device.online,
    _connectionStatus: envelope.device.connection_status,
    _ageSeconds: envelope.device.age_seconds,
    _receivedAt: envelope.device.last_seen,
  };
  if (envelope.data && (envelope.data.vitals || envelope.data.health)) return {
    ...envelope.data,
    device_id: envelope.device_id || deviceId,
    node_type: envelope.node_type || "smart_hospital_ward",
    _receivedAt: envelope.timestamp,
  };
  if (envelope.vitals || envelope.health) return envelope;
  return null;
}

export function adaptHospitalWard(payload) {
  if (!payload) return null;
  const health = payload.health || {};
  const connectionStatus = payload._connectionStatus || (payload._online === false ? "OFFLINE" : "LIVE");
  const telemetryUsable = connectionStatus !== "OFFLINE";
  const vitalsOnline = telemetryUsable && health.max30100 !== false;
  const vitalsValid = Boolean(vitalsOnline && payload.vitals?.valid);
  const pmsOnline = telemetryUsable && health.pms5003 !== false;
  const lightOnline = telemetryUsable && health.bh1750 !== false;
  const bmpOnline = telemetryUsable && health.bmp180 !== false;
  const binOnline = telemetryUsable && health.ultrasonic !== false && payload.bin?.valid !== false;
  const airOnline = telemetryUsable && health.mq !== false;
  const vibrationOnline = telemetryUsable && health.vibration !== false;
  const waitingForPatient = vitalsOnline && !vitalsValid;
  return {
    id: payload.device_id || WARD_DEVICE_ID,
    nodeType: payload.node_type || "smart_hospital_ward",
    online: connectionStatus === "LIVE",
    connectionStatus,
    ageSeconds: hasNumber(payload._ageSeconds) ? payload._ageSeconds : null,
    uptimeMs: payload.uptime_ms || 0,
    updatedAt: normalizeTimestamp(payload._receivedAt || payload.timestamp),
    connectivity: {
      wifi: Boolean(health.wifi),
      wifiRssi: hasNumber(health.wifi_rssi) ? health.wifi_rssi : null,
      mqtt: Boolean(health.mqtt),
    },
    modules: {
      vitals: vitalsOnline,
      particulate: pmsOnline,
      light: lightOnline,
      climate: bmpOnline,
      bin: binOnline,
      rfid: telemetryUsable && health.rc522 !== false,
      air: airOnline,
      vibration: vibrationOnline,
      panicButton: telemetryUsable && health.panic_button !== false,
      oled: telemetryUsable && health.oled !== false,
    },
    bed: {
      vibration: vibrationOnline ? Boolean(payload.bed?.vibration) : null,
      status: vibrationOnline ? payload.bed?.status || (payload.bed?.vibration ? "vibration_detected" : "stable") : "offline",
      available: vibrationOnline,
    },
    vitals: {
      heartRate: reading(vitalsValid, payload.vitals?.heart_rate, " bpm", waitingForPatient ? "Waiting for patient" : "Sensor Offline"),
      spo2: reading(vitalsValid, payload.vitals?.spo2, "%", waitingForPatient ? "Waiting for patient" : "Sensor Offline"),
      valid: vitalsValid,
      waitingForPatient,
      attention: vitalsValid ? Boolean(payload.vitals?.attention) : false,
    },
    environment: {
      temperature: reading(bmpOnline, payload.environment?.temperature_c, " °C"),
      pressure: reading(bmpOnline, payload.environment?.pressure_hpa, " hPa"),
      pm1: reading(pmsOnline, payload.environment?.pm1, " µg/m³"),
      pm25: reading(pmsOnline, payload.environment?.pm25, " µg/m³"),
      pm10: reading(pmsOnline, payload.environment?.pm10, " µg/m³"),
      lux: reading(lightOnline, payload.environment?.lux, " lux"),
    },
    air: {
      available: airOnline,
      adc: airOnline && hasNumber(payload.air?.adc) ? payload.air.adc : null,
      gpioVoltage: airOnline && hasNumber(payload.air?.gpio_voltage) ? payload.air.gpio_voltage : null,
      sensorVoltage: airOnline && hasNumber(payload.air?.sensor_voltage) ? payload.air.sensor_voltage : null,
      baselineReady: airOnline ? Boolean(payload.air?.baseline_ready) : false,
      anomaly: airOnline ? Boolean(payload.air?.anomaly) : false,
    },
    bin: {
      available: binOnline,
      distanceCm: binOnline && hasNumber(payload.bin?.distance_cm) ? payload.bin.distance_cm : null,
      fillPercent: binOnline && hasNumber(payload.bin?.fill_percent) ? payload.bin.fill_percent : null,
      full: binOnline ? Boolean(payload.bin?.full) : false,
    },
    emergency: {
      available: telemetryUsable && health.panic_button !== false,
      panic: Boolean(payload.emergency?.panic),
      status: telemetryUsable && health.panic_button !== false ? payload.emergency?.status || "NORMAL" : "OFFLINE",
    },
    rfid: {
      available: telemetryUsable && health.rc522 !== false,
      lastUid: payload.rfid?.last_uid && payload.rfid.last_uid !== "NONE" ? payload.rfid.last_uid : null,
    },
    rawHealth: health,
  };
}

export function adaptHospitalEnvelope(envelope, deviceId = WARD_DEVICE_ID) {
  const payload = extractHospitalWard(envelope, deviceId);
  return payload ? adaptHospitalWard(payload) : null;
}

const healthLabels = {
  wifi:"Wi-Fi", mqtt:"MQTT transport", bh1750:"BH1750 light", max30100:"MAX30100 vitals",
  bmp180:"BMP180 climate", oled:"OLED display", pms5003:"PMS5003 particulate",
  ultrasonic:"Ultrasonic bin", rc522:"RC522 RFID", mq:"MQ air/vapor", vibration:"Vibration sensor",
  panic_button:"Panic button",
};

export function moduleStatus(model) {
  if (!model) return [];
  return Object.entries(healthLabels)
    .filter(([key]) => Object.prototype.hasOwnProperty.call(model.rawHealth, key))
    .map(([key,label]) => {
      const ok = model.connectionStatus !== "OFFLINE" && Boolean(model.rawHealth[key]);
      return { key, label, ok, severity: ok ? "healthy" : key === "mqtt" || key === "panic_button" ? "critical" : "unavailable" };
    });
}
