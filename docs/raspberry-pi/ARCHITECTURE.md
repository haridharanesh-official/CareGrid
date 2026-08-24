# Raspberry Pi Control Unit Architecture

## Purpose

The Raspberry Pi 4 is the central edge gateway for the CareGrid hospital prototype. It bridges hospital IoT nodes, the Smart Ambulance, Home Assistant, and local automation services.

The Pi should continue operating on the hospital LAN even when Internet connectivity is unavailable.

## Responsibilities

1. Run the local MQTT broker used by trusted CareGrid devices.
2. Receive telemetry from ESP32 hospital nodes.
3. Receive Smart Ambulance status and emergency telemetry.
4. Validate message structure, source identity, timestamps, and acceptable value ranges.
5. Normalize device-specific messages into the CareGrid data model.
6. Publish normalized states for Home Assistant.
7. Maintain device online/offline health.
8. Generate system alerts from configured rules.
9. Store important events locally for debugging and demonstration.
10. Expose a controlled REST API for integrations that cannot use MQTT.
11. Provide service health endpoints and operational logs.

## Proposed Runtime Stack

- Raspberry Pi 4
- Raspberry Pi OS 64-bit
- Docker Compose for reproducible service deployment where appropriate
- Eclipse Mosquitto for MQTT
- Python 3 for the CareGrid Gateway
- FastAPI for REST endpoints
- Pydantic for payload validation
- SQLite initially for local event persistence
- Home Assistant for dashboards and operator monitoring
- systemd/Docker restart policies for service recovery

## Logical Data Flow

```text
ESP32 Hospital Nodes -------- MQTT --------+
                                          |
Smart Ambulance ----- MQTT / REST API -----+--> CareGrid Gateway
                                          |        |
                                          |        +--> validation
                                          |        +--> normalization
                                          |        +--> alert rules
                                          |        +--> event logging
                                          |        +--> device health
                                          |        |
                                          |        v
                                          +----> MQTT normalized topics
                                                   |
                                                   v
                                             Home Assistant
```

## Control Boundary

CareGrid separates telemetry ingestion from actuator control.

Untrusted or malformed device messages must never directly switch hospital hardware. Incoming data is validated first. Any future actuator command must pass through an explicit control policy and must be auditable.

## Failure Behaviour

### ESP32 node offline
The gateway marks the device unavailable after a configured heartbeat timeout. Other nodes continue operating.

### Ambulance connection lost
The last known state is retained with a stale/offline marker. Hospital sensor monitoring continues.

### Home Assistant unavailable
MQTT and gateway ingestion continue. Home Assistant can recover current retained state after restart.

### Internet unavailable
Hospital-local MQTT, gateway processing, local dashboards, and local event storage should remain operational.

### Gateway process crash
The service manager automatically restarts the process. Logs preserve the failure context.

## Initial MQTT Namespace

```text
caregrid/raw/<device_id>/telemetry
caregrid/raw/<device_id>/status
caregrid/state/<device_id>/<metric>
caregrid/alert/<severity>/<alert_id>
caregrid/system/gateway/status
caregrid/system/device/<device_id>/availability
```

Raw topics are ingestion channels. `caregrid/state/...` topics contain validated/normalized data suitable for Home Assistant.

## Raspberry Pi Development Phases

### Phase 1 — Foundation
- OS and networking baseline
- repository structure
- environment configuration
- Mosquitto
- service user and permissions
- gateway skeleton

### Phase 2 — Device Ingestion
- device registry
- MQTT subscriber
- telemetry schemas
- validation
- heartbeat/availability

### Phase 3 — Home Assistant
- normalized state topics
- MQTT Discovery
- hospital dashboard entities
- alert entities

### Phase 4 — Ambulance Integration
- authenticated REST endpoint
- ambulance telemetry model
- emergency arrival/status events
- Home Assistant ambulance dashboard

### Phase 5 — Reliability
- SQLite event history
- structured logs
- service watchdogs
- reconnect handling
- test simulator
- soak testing

### Phase 6 — SIH Demo Hardening
- automated setup
- backup/recovery instructions
- demo mode
- failure demonstrations
- final architecture and deployment documentation
