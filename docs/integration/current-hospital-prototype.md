# Current CareGrid Hospital Prototype

This document is the source of truth for the currently tested hospital-side prototype.

## Active ESP32-S3 hardware

| Module | Purpose | Interface |
|---|---|---|
| BH1750 | Light level | I2C GPIO8/9 |
| MAX30100 | Prototype HR/SpO2 | I2C GPIO8/9 |
| BMP180 | Temperature/pressure | I2C GPIO8/9 |
| SSD1306 OLED | Local display | I2C GPIO8/9 |
| PMS5003 | PM1/PM2.5/PM10 | UART GPIO12/13 |
| HC-SR04 | Medical waste-bin level | GPIO10/11 |
| RC522 | RFID | SPI GPIO14-18 |
| MQ analog sensor | Relative vapor/air anomaly | ADC GPIO1 |
| Vibration sensor | Bed movement | GPIO6 |
| Panic button | Patient emergency alert | GPIO21 |

Removed from the active prototype: HX711/load cell, PIR, mmWave, MPU6050, GY-271, AC detector, SCD40, LoRa and ESP32-side RTC.

## Safety wiring

HC-SR04 ECHO and MQ analog output use the tested divider:

```text
Sensor output -> 10K -> ESP32 input -> 20K -> GND
```

The panic button uses `INPUT_PULLUP`: released=HIGH, pressed=LOW. The tested vibration sensor uses LOW=stable and HIGH=vibration.

## MQTT

```text
caregrid/hospital/ward/ward-01/telemetry
caregrid/hospital/ward/ward-01/status
caregrid/hospital/ward/ward-01/rfid
caregrid/hospital/ward/ward-01/panic
```

Panic payloads are plain text: `EMERGENCY` and `NORMAL`.

Telemetry uses the canonical envelope:

```json
{
  "device_id": "hospital_ward_01",
  "node_type": "smart_hospital_ward",
  "data": {
    "vitals": {},
    "environment": {},
    "bin": {},
    "bed": {},
    "emergency": {},
    "air": {},
    "rfid": {},
    "health": {}
  }
}
```

## Raspberry Pi gateway

The Pi gateway maps `caregrid/hospital/ward/ward-01/...` to the single internal id `hospital_ward_01`. Panic/status messages are handled separately from telemetry JSON.

Realtime frontend contract:

```text
GET /api/hospital/latest
GET /api/hospital/{device_id}
GET /api/emergencies/recent
WS  /ws/hospital
```

The frontend should fetch initial state once and then use WebSocket updates instead of frequent polling.

## Home Assistant

The gateway publishes state to:

```text
caregrid/state/hospital_ward_01
```

Current MQTT Discovery covers vitals, environmental values, particulate readings, bin status, bed vibration, panic, MQ state, RFID and sensor health.

Stale retained discovery topics from older mmWave/load-cell/AC-supply firmware must be individually cleared with an empty retained MQTT publication. Do not erase unrelated Home Assistant discovery topics.

## Verified end-to-end behavior

- ESP32 telemetry reaches Mosquitto.
- Raspberry Pi gateway connects to local MQTT.
- Canonical hospital node id is `hospital_ward_01`.
- REST `/api/hospital/latest` responds successfully.
- Frontend WebSocket `/ws/hospital` connects successfully.
- Panic press produces an immediate `EMERGENCY` event.
- Panic release produces an immediate `NORMAL` event.

MAX30100 is prototype/non-clinical. MQ values are relative anomaly indicators and not calibrated gas concentration measurements.
