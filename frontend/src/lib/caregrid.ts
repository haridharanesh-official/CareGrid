export type ConnectionStatus = "LIVE" | "STALE" | "OFFLINE";

export interface CareGridVitals {
  valid?: boolean;
  heart_rate?: number | null;
  spo2?: number | null;
}

export interface CareGridEnvironment {
  lux?: number | null;
  temperature_c?: number | null;
  pressure_hpa?: number | null;
  pm1?: number | null;
  pm25?: number | null;
  pm10?: number | null;
}

export interface CareGridBin {
  valid?: boolean;
  distance_cm?: number | null;
  fill_percent?: number | null;
  full?: boolean;
}

export interface CareGridBed {
  vibration?: boolean;
  status?: string;
}

export interface CareGridEmergency {
  panic?: boolean;
  status?: string;
  updated_at?: string;
}

export interface CareGridAir {
  adc?: number | null;
  gpio_voltage?: number | null;
  sensor_voltage?: number | null;
  baseline_ready?: boolean;
  anomaly?: boolean;
}

export interface CareGridRfid {
  last_uid?: string;
}

export interface CareGridHealth {
  wifi?: boolean;
  wifi_rssi?: number | null;
  mqtt?: boolean;
  bh1750?: boolean;
  max30100?: boolean;
  bmp180?: boolean;
  oled?: boolean;
  pms5003?: boolean;
  ultrasonic?: boolean;
  rc522?: boolean;
  mq?: boolean;
  vibration?: boolean;
  panic_button?: boolean;
}

export interface CareGridNodeData {
  uptime_ms?: number;
  vitals?: CareGridVitals;
  environment?: CareGridEnvironment;
  bin?: CareGridBin;
  bed?: CareGridBed;
  emergency?: CareGridEmergency;
  air?: CareGridAir;
  rfid?: CareGridRfid;
  health?: CareGridHealth;
}

export interface CareGridNode {
  device_id: string;
  node_type: string;
  last_seen: string | null;
  online: boolean;
  connection_status: ConnectionStatus;
  age_seconds: number | null;
  mqtt_status?: "online" | "offline";
  mqtt_status_updated_at?: string;
  data: CareGridNodeData;
}

export interface HospitalLatestResponse {
  status: string;
  timestamp: string;
  nodes: Record<string, CareGridNode>;
}

export interface HospitalWebSocketMessage {
  type: "hospital_update";
  timestamp: string;
  nodes: Record<string, CareGridNode>;
}
