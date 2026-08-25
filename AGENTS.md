# CareGrid — Codex Repository Instructions

## Project

CareGrid is a Smart Hospital Automation and Connected Emergency Response prototype.

## Core architecture

```text
Hospital sensors
-> ESP32-S3
-> Wi-Fi / MQTT
-> Mosquitto on Raspberry Pi
-> FastAPI gateway
-> SQLite
-> REST + WebSocket
-> CareGrid frontend
```

Home Assistant also receives trusted MQTT state from the Raspberry Pi gateway.

The frontend must NEVER connect directly to MQTT.

## Raspberry Pi backend

Backend directory:

```text
raspberry-pi/
```

Primary API application:

```text
raspberry-pi/app/main.py
```

The gateway runs on port 8000.

Typical development address:

```text
http://10.15.43.187:8000
```

Do not hardcode this across frontend components. Use environment configuration.

## Current hospital node

Canonical device id:

```text
hospital_ward_01
```

Node type:

```text
smart_hospital_ward
```

MQTT topics:

```text
caregrid/hospital/ward/ward-01/telemetry
caregrid/hospital/ward/ward-01/status
caregrid/hospital/ward/ward-01/rfid
caregrid/hospital/ward/ward-01/panic
```

Panic payloads:

```text
EMERGENCY
NORMAL
```

## Canonical telemetry

Telemetry MUST contain:

```json
{
  "device_id": "hospital_ward_01",
  "node_type": "smart_hospital_ward",
  "data": {}
}
```

Never remove the `data` envelope.

## Current hospital sensors

Active:

- BH1750
- MAX30100
- BMP180
- PMS5003
- HC-SR04
- RC522 RFID
- MQ analog sensor
- vibration sensor
- SSD1306 OLED
- panic button

Removed / inactive:

- HX711
- load cell
- PIR
- 24 GHz mmWave
- MPU6050
- GY-271
- AC detector
- SCD40
- LoRa

Do not reintroduce removed sensors into active code or UI.

## ESP32 pin mapping

```text
GPIO1  = MQ analog
GPIO6  = vibration
GPIO8  = I2C SDA
GPIO9  = I2C SCL
GPIO10 = HC-SR04 TRIG
GPIO11 = HC-SR04 ECHO
GPIO12 = PMS5003 RX
GPIO13 = PMS5003 TX
GPIO14 = RC522 SCK
GPIO15 = RC522 MOSI
GPIO16 = RC522 MISO
GPIO17 = RC522 CS
GPIO18 = RC522 RST
GPIO21 = panic button
```

Do not change the pinout unless explicitly requested.

## Sensor truth rules

Never fabricate realtime values.

MAX30100:

If `valid == false`:

```text
heart_rate = null
spo2 = null
```

Frontend should display:

```text
Waiting for patient
```

Do not convert invalid readings to zero.

PMS5003 unavailable: do not fabricate PM values.

Bed vibration is NOT bed occupancy.

## Node connectivity rules

ESP32 telemetry interval is approximately 5 seconds.

Backend derives physical node state from telemetry freshness:

```text
<=15 seconds:
LIVE

>15 and <=30 seconds:
STALE

>30 seconds:
OFFLINE
```

A retained MQTT `online` message must NOT refresh `last_seen`.

A retained panic message must NOT refresh `last_seen`.

Only actual telemetry proves current device liveness.

Gateway state and ward node state are separate concepts.

## Existing FastAPI endpoints

```text
GET /
GET /health

GET /devices
GET /devices/{device_id}

GET /events/recent

GET /api/hospital/latest
GET /api/hospital/{device_id}

GET /api/emergencies/recent

WS /ws/hospital
```

Preserve them unless a migration is explicitly required.

## Frontend realtime model

Initial fetch:

```text
GET /api/hospital/latest
```

Then:

```text
WS /ws/hospital
```

Do not continuously poll the backend every second when WebSocket is functioning.

Implement reconnect behavior.

Frontend connection indicators:

```text
Gateway:
LIVE / RECONNECTING / OFFLINE

Individual node:
LIVE / STALE / OFFLINE
```

## Panic

Panic is high priority.

When `panic == true`: show a prominent realtime alert.

Example:

```text
PATIENT PANIC ALERT — WARD 01
```

Never silently hide or fabricate panic events.

## Demo RFID assignments

```text
D0:DA:F6:5F -> Balaji / PATIENT-001
1D:69:50:06 -> Akshitha / PATIENT-002
53:67:70:56 -> Lekha / PATIENT-003
AA:B4:32:06 -> Dr. Hari / DOC-001
```

Reserved:

```text
04:06:96:04
76:4D:32:06
43:E7:50:06
```

These are demo records.

## Demo patient records

```text
Balaji
PATIENT-001
Blood group: O+

Akshitha
PATIENT-002
Blood group: B+

Lekha
PATIENT-003
Blood group: A+
Demo condition label: Smile disorder

Doctor:
Hari
DOC-001
Emergency Medicine
```

Do not present demo records as real clinical data.

## Hospital functionality

System should eventually support:

- hospital availability
- departments
- bed management
- pharmacy inventory
- patient records
- RFID lookup
- emergency routing
- pre-alerts
- nurse portal
- doctor portal
- ambulance portal
- history
- panic events
- realtime telemetry

## Medical safety language

MAX30100 is prototype/non-clinical monitoring.

MQ sensor is a relative anomaly signal, not a calibrated clinical gas measurement.

Do not claim medical-grade diagnosis.

## Repository security

Never commit:

- `.env`
- Wi-Fi passwords
- MQTT passwords
- GitHub passwords
- personal access tokens
- API secrets
- SQLite runtime databases
- `node_modules`
- `.venv`
- `__pycache__`

Use `.env.example`.

## Development behavior

Before changing code:

1. inspect only relevant files
2. understand current implementation
3. avoid unrelated refactors
4. preserve working features
5. change the minimum necessary files
6. test the affected area
7. report exactly what changed

Do not rebuild the entire project unless explicitly requested.

## Testing

Backend minimum:

```bash
python -m py_compile raspberry-pi/app/main.py
```

Run available backend tests when present.

Frontend minimum:

```bash
npm run typecheck
```

Then relevant lint/tests.

Run full build only after meaningful feature completion rather than after every small edit.

Do not claim physical hardware tests were run unless actual hardware was available.

## Completion format

At the end of every task report:

- files changed
- behavior implemented
- tests run
- test results
- unresolved issues
- hardware verification still required

Do not push unless the current task explicitly asks you to push.
