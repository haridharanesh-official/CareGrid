# ESP32-S3 Hospital Sensor Controller Integration

Status: Prototype working; Raspberry Pi integration in progress.

## Purpose

The ESP32-S3 Hospital Sensor Controller is the primary hospital-side sensing node for CareGrid. It sends validated telemetry to the Raspberry Pi control unit over MQTT. The Raspberry Pi is the trusted gateway that records data, exposes APIs, evaluates alerts, and forwards state to Home Assistant.

## Data Flow

```text
Hospital Sensors
      |
      v
ESP32-S3 Hospital Sensor Controller
      |
      | Wi-Fi + MQTT
      v
Mosquitto on Raspberry Pi
      |
      v
CareGrid Gateway
      |
      +--> SQLite event history
      +--> Current device state
      +--> Alert processing
      +--> REST API
      +--> Home Assistant MQTT discovery/state
```

## MQTT Broker

- Host: Raspberry Pi LAN address
- Port: 1883
- Authentication: required
- Anonymous MQTT: disabled
- Credentials must not be stored in GitHub

## Primary Telemetry Topic

```text
caregrid/hospital/controller/hospital-01/telemetry
```

Additional nodes may follow:

```text
caregrid/hospital/<node-type>/<device-id>/telemetry
```

## Telemetry Envelope

Every ESP32 message sent to the CareGrid gateway must use this outer structure:

```json
{
  "device_id": "hospital-01",
  "node_type": "hospital_sensor_controller",
  "data": {
    "example_sensor": 1
  }
}
```

Optional timestamp:

```json
{
  "device_id": "hospital-01",
  "node_type": "hospital_sensor_controller",
  "timestamp": "2026-08-24T08:30:00Z",
  "data": {}
}
```

## Recommended Data Keys

Only keys for sensors physically present in the working prototype should be transmitted. The gateway is intentionally generic so new sensor values can be introduced without changing the MQTT envelope.

Examples of CareGrid hospital telemetry include:

- `heart_rate`
- `spo2`
- `presence`
- `occupancy`
- `pm25`
- `pm10`
- `lux`
- `alcohol_alert`
- `temperature`
- `humidity`

Do not send fabricated values for sensors that are not connected.

## Device Availability

The Raspberry Pi gateway publishes retained availability state under:

```text
caregrid/devices/<device-id>/availability
```

Expected values:

```text
online
offline
```

## Current State

Latest normalized state is published by the Raspberry Pi under:

```text
caregrid/devices/<device-id>/state
```

The ESP32 should publish only raw/processed telemetry to its telemetry topic. It should not publish directly to Home Assistant discovery topics.

## Safety Boundary

The ESP32-S3 is a sensor/edge node. CareGrid follows these rules:

1. ESP32 sends telemetry to the Raspberry Pi.
2. Raspberry Pi validates the message.
3. Raspberry Pi records and normalizes the data.
4. Alert/automation logic runs at the trusted gateway/Home Assistant layer.
5. Unvalidated external MQTT messages must not directly trigger safety-critical hardware.

## Integration Verification

The real ESP32-to-Raspberry-Pi test is complete only when all of the following pass:

1. ESP32 connects to the authenticated Mosquitto broker.
2. MQTT telemetry appears on the Raspberry Pi.
3. CareGrid gateway accepts the JSON envelope.
4. `/devices` shows `hospital-01`.
5. `/events/recent` contains the telemetry event.
6. SQLite contains the event.
7. Home Assistant receives the generated discovery/state topics after installation.

## Secrets

Wi-Fi passwords, MQTT passwords, tokens, and API keys must remain in local configuration or firmware secrets files excluded from Git.
