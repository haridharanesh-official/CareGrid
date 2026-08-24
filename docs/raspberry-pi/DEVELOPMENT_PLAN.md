# Raspberry Pi Control Unit Development Plan

This document tracks implementation work for the CareGrid Raspberry Pi control unit.

## Milestone 1 — Pi Foundation

- [ ] Install/update Raspberry Pi OS 64-bit
- [ ] Set hostname to `caregrid-pi`
- [ ] Configure stable LAN connectivity
- [ ] Enable SSH securely
- [ ] Set system timezone
- [ ] Install Git, Python, Docker, and required tooling
- [ ] Create CareGrid service directories
- [ ] Configure `.env`-based secrets
- [ ] Add `.gitignore`

## Milestone 2 — MQTT Backbone

- [ ] Install Mosquitto
- [ ] Disable anonymous remote access
- [ ] Create dedicated MQTT credentials
- [ ] Configure persistence
- [ ] Configure retained system status
- [ ] Establish CareGrid MQTT topic convention
- [ ] Test ESP32 -> Pi publish
- [ ] Test Pi -> Home Assistant state delivery

## Milestone 3 — CareGrid Gateway

- [ ] Python project structure
- [ ] configuration loader
- [ ] structured logging
- [ ] MQTT connection manager
- [ ] telemetry router
- [ ] Pydantic message schemas
- [ ] device registry
- [ ] metric normalization
- [ ] heartbeat manager
- [ ] graceful shutdown
- [ ] health endpoint

## Milestone 4 — Hospital Nodes

Integrate the hospital automation subsystems as logical CareGrid devices:

- [ ] Smart Patient Bed Node
- [ ] Bedside Patient Vital Node
- [ ] Ward Presence Node
- [ ] Smart Ward Environment Node
- [ ] Hospital Air/Alcohol/VOC Alert Node

## Milestone 5 — Smart Ambulance

- [ ] Ambulance device identity
- [ ] authenticated REST/MQTT ingestion
- [ ] emergency type
- [ ] ambulance status
- [ ] patient vital telemetry
- [ ] location/GPS telemetry where available
- [ ] ETA field/interface
- [ ] crash/motion event
- [ ] driver safety event
- [ ] hospital arrival workflow

## Milestone 6 — Home Assistant

- [ ] MQTT integration
- [ ] MQTT Discovery generator
- [ ] device availability
- [ ] bed occupancy entities
- [ ] patient vital entities
- [ ] ward presence entities
- [ ] environmental entities
- [ ] ambulance entities
- [ ] alert entities
- [ ] CareGrid system-health dashboard

## Milestone 7 — Persistence and Alerts

- [ ] SQLite event database
- [ ] alert table/model
- [ ] configurable thresholds
- [ ] deduplication/cooldown
- [ ] acknowledgement state
- [ ] event export for SIH demonstration

## Milestone 8 — Reliability and Security

- [ ] least-privilege service account
- [ ] secrets excluded from Git
- [ ] MQTT authentication
- [ ] API authentication
- [ ] input limits
- [ ] schema validation
- [ ] replay/stale-message protection where practical
- [ ] watchdog/restart policy
- [ ] disk/log rotation
- [ ] offline LAN operation
- [ ] recovery documentation

## Milestone 9 — Verification

- [ ] unit tests
- [ ] MQTT integration tests
- [ ] API tests
- [ ] simulated ESP32 telemetry
- [ ] simulated ambulance telemetry
- [ ] malformed-payload tests
- [ ] disconnect/reconnect tests
- [ ] Home Assistant restart test
- [ ] gateway restart test
- [ ] Pi reboot test
- [ ] demo soak test

## Git Contribution Policy

All team members should work through identifiable GitHub commits. Avoid collecting an entire subsystem into one final commit. Commit architecture, implementation, tests, fixes, and documentation as meaningful increments so SIH evaluators can see continuous team participation.

Recommended commit prefixes:

```text
feat:     new functionality
fix:      bug fix
docs:     documentation
test:     tests
refactor: internal restructuring
chore:    tooling/configuration
```
