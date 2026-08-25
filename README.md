# CareGrid

CareGrid is a Smart Hospital Automation and Connected Emergency Response platform being developed for SIH 2026. The current working prototype focuses on a hospital ward node built around an ESP32-S3, a Raspberry Pi 4 edge gateway, Mosquitto MQTT, FastAPI, SQLite, Home Assistant, and a realtime web frontend.

## Working Hospital Prototype

The active hospital ward node currently uses:

- BH1750 — ward light level
- MAX30100 — prototype heart-rate and SpO2 monitoring
- BMP180 — temperature and atmospheric pressure
- PMS5003 — PM1 / PM2.5 / PM10
- HC-SR04 — medical-waste bin distance/fill estimate
- RC522 — RFID identification
- MQ analog sensor — relative air/vapor anomaly signal
- vibration sensor — bed movement/vibration
- SSD1306 OLED — local bedside display
- panic push button — immediate patient emergency alert

Removed from the current prototype: HX711/load cell, PIR, 24 GHz mmWave, MPU6050, GY-271, AC detector, SCD40, LoRa, and ESP32-side RTC.

> MAX30100 readings are prototype/non-clinical. The MQ sensor is treated as a relative anomaly signal, not a calibrated gas concentration instrument.

## Frozen ESP32-S3 Pinout

```text
GPIO1  = MQ analog
GPIO6  = vibration sensor
GPIO8  = I2C SDA
GPIO9  = I2C SCL
GPIO10 = HC-SR04 TRIG
GPIO11 = HC-SR04 ECHO (through 10K/20K divider)
GPIO12 = PMS5003 TX -> ESP32 RX
GPIO13 = PMS5003 RX <- ESP32 TX
GPIO14 = RC522 SCK
GPIO15 = RC522 MOSI
GPIO16 = RC522 MISO
GPIO17 = RC522 SDA / SPI CS
GPIO18 = RC522 RST
GPIO21 = panic button
```

Shared I2C on GPIO8/GPIO9: BH1750, MAX30100, BMP180 and SSD1306 OLED.

Panic button wiring: `GPIO21 -> push button -> GND`, using `INPUT_PULLUP` (`HIGH = released`, `LOW = pressed`).

Vibration sensor logic on the tested module: `LOW = stable`, `HIGH = vibration` with a short hold period to preserve brief pulses.

The MQ analog output and HC-SR04 ECHO must use the tested 10K/20K resistor divider before the ESP32 input.

## Architecture

```text
Hospital sensors
      |
      v
   ESP32-S3
      |
   Wi-Fi/MQTT
      |
      v
 Mosquitto Broker
      |
      v
 Raspberry Pi 4
      |
 +----+-------------------+
 | FastAPI Gateway        |
 | SQLite event history   |
 | Home Assistant MQTT    |
 | REST + WebSocket API   |
 +----+-------------------+
      |
      v
CareGrid Frontend / Home Assistant
```

## MQTT Topics

```text
caregrid/hospital/ward/ward-01/telemetry
caregrid/hospital/ward/ward-01/status
caregrid/hospital/ward/ward-01/rfid
caregrid/hospital/ward/ward-01/panic
```

Panic uses plain retained payloads:

```text
EMERGENCY
NORMAL
```

Canonical telemetry envelope:

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

The Raspberry Pi maps the MQTT path `ward-01` to the canonical internal device id `hospital_ward_01`, so telemetry, panic and online/offline status remain one device.

## Raspberry Pi Gateway

The gateway runs from `/opt/caregrid/raspberry-pi` and provides:

```text
GET /
GET /health
GET /devices
GET /devices/{device_id}
GET /events/recent
GET /api/hospital/latest
GET /api/hospital/{device_id}
GET /api/emergencies/recent
WS  /ws/hospital
```

Frontend integration should fetch `/api/hospital/latest` once for initial state and then use `/ws/hospital` for realtime updates instead of high-frequency polling.

The panic MQTT topic is handled separately from telemetry JSON so `EMERGENCY` / `NORMAL` never enter the Pydantic telemetry parser.

## Home Assistant

The Raspberry Pi publishes the current nested CareGrid state to:

```text
caregrid/state/hospital_ward_01
```

and publishes MQTT Discovery entities for the current prototype, including heart rate, SpO2, light, temperature, pressure, PM values, medical waste-bin status, bed vibration, panic button, MQ signal, RFID and sensor-health indicators.

Old retained discovery entities from previous hardware revisions (mmWave, bed-load/load-cell, old occupancy and AC-supply entities) should be deleted individually from their retained `homeassistant/.../config` topics. Do not wipe unrelated Home Assistant discovery topics.

## Raspberry Pi Service

The gateway should be managed by systemd and restart automatically. Typical deployment:

```bash
sudo systemctl daemon-reload
sudo systemctl enable caregrid
sudo systemctl restart caregrid
sudo systemctl status caregrid
```

## Repository Security

Real Wi-Fi passwords, MQTT passwords, API keys and tokens must never be committed. Use `.env` locally and keep only `.env.example` / placeholder configuration in GitHub.

Runtime databases, virtual environments, Node modules, build output and secrets are ignored by `.gitignore`.

## Current Verified Flow

```text
ESP32 telemetry -> Mosquitto -> Raspberry Pi FastAPI -> REST/WebSocket -> frontend
                                      |
                                      +-> SQLite
                                      +-> Home Assistant MQTT

Panic press -> MQTT EMERGENCY -> Raspberry Pi -> immediate live state / alert
Panic release -> MQTT NORMAL -> Raspberry Pi -> resolved state
```

The tested backend has successfully received telemetry, mapped the hospital node as `hospital_ward_01`, accepted frontend WebSocket connections, and detected panic press/release events in realtime.
