# CareGrid

CareGrid is a Smart Hospital Automation and Connected Emergency Response platform being developed for SIH 2026.

This repository contains the complete system, including the Raspberry Pi hospital control unit, ESP32 sensor nodes, Smart Ambulance integration, Home Assistant dashboards, APIs, automation logic, documentation, and demo assets.

## Current Development Focus

### Raspberry Pi Control Unit
The Raspberry Pi acts as the central hospital edge gateway and control plane. It receives telemetry from distributed ESP32 nodes and the Smart Ambulance, validates and normalizes incoming data, publishes trusted state to Home Assistant, manages MQTT/API communication, records events, and provides health monitoring for the overall CareGrid system.

## Planned High-Level Architecture

```text
Hospital Sensor Nodes / Smart Ambulance
            |
       Wi-Fi / MQTT / HTTP
            |
            v
+-----------------------------+
| Raspberry Pi Control Unit   |
|-----------------------------|
| MQTT Broker                 |
| CareGrid Gateway Service    |
| REST API                    |
| Validation + Normalization  |
| Event / Alert Engine        |
| Device Health Monitor       |
| Local Event Storage         |
| Home Assistant Integration  |
+-----------------------------+
            |
            v
      Home Assistant
      Hospital Dashboard
```

## Repository Structure

```text
CareGrid/
├── README.md
├── docs/
│   └── raspberry-pi/
├── raspberry-pi/
│   ├── app/
│   ├── config/
│   ├── scripts/
│   ├── tests/
│   └── systemd/
├── esp32/
├── home-assistant/
├── ambulance/
└── hardware/
```

## Development Rules

- Every meaningful feature must be committed to GitHub so team contributions remain identifiable.
- Secrets, Wi-Fi passwords, API keys, and tokens must never be committed.
- Home Assistant is the primary monitoring/dashboard layer.
- ESP32 and ambulance devices send telemetry to the Raspberry Pi; the Pi is responsible for validation and integration.
- Safety-critical hardware actions must not be triggered directly by unvalidated external messages.
- Hardware integrations must support graceful failure and device-health reporting.

## Current Status

- [x] Repository initialized
- [x] Raspberry Pi control-unit architecture defined
- [ ] Raspberry Pi OS provisioning
- [ ] Mosquitto MQTT broker configuration
- [ ] CareGrid gateway service
- [ ] Device registry and telemetry schema
- [ ] Home Assistant MQTT discovery
- [ ] Ambulance-to-hospital API
- [ ] Alert engine
- [ ] Persistent event logging
- [ ] Service health monitoring
- [ ] End-to-end integration tests

## Project

**CareGrid — Smart Hospital Automation and Connected Emergency Response System**
