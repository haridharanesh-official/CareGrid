# CareGrid frontend architecture

## Product boundary

This repository is the frontend for CareGrid, a smart-hospital automation and connected emergency-response platform. It does not contain the future clinical database or modify the Raspberry Pi/ESP32 firmware. The frontend treats the Raspberry Pi gateway as the live sensor authority and the future CareGrid application API as a replaceable service dependency.

## Application composition and roles

`src/app/App.jsx` composes providers and the React Router tree. `src/app/router.jsx` owns `/login`, `/ambulance/*`, `/nurse/*`, and `/doctor/*`. `AuthGate` requires a session and `RoleGate` prevents a logged-in role from opening another portal directly. Authentication lives in `AuthProvider`; pages never read or write browser session storage directly.

The three role layouts share brand, live connection state, system status, sign-out, and navigation behavior through `RoleLayout`. Each visible navigation item points to an implemented operational page. The role switcher is rendered only when `VITE_DEMO_MODE=true`.

## API and data-source boundary

`caregridApi.js` supplies the base URL, timeout, JSON handling, and safe errors. The gateway addresses come from `VITE_CAREGRID_API_URL` and `VITE_CAREGRID_WS_URL`. The hospital realtime layer currently calls:

- `GET /api/hospital/latest` for bootstrap and safety refreshes while realtime is unavailable.
- `WS /ws/hospital` for immediate replacement snapshots.

An HTTP 404 from the new latest-state route activates a temporary real-data-only compatibility request to `GET /devices/hospital_ward_01` and `GET /health`. No MQTT client or credential exists in the browser bundle.

Future domains have separate services: patient, ambulance, hospital, pharmacy, medication, and bed. Components call those functions without knowing whether the implementation is demo or remote. Today those future calls are enabled only in demo mode and fail with an explicit “backend is not connected” error when demo mode is disabled.

## Demo mode and data provenance

Demo records are isolated under `src/mock`. `VITE_DEMO_MODE=true` enables complete local workflows. The UI always labels fallback records and gateway fallback as `Demo Data`. A reachable live gateway has priority even in demo mode. With demo mode disabled, gateway failure produces `CareGrid Gateway Offline`; no fake telemetry is substituted.

Demo session identity is stored in `sessionStorage`, not `localStorage`, and contains only role and display name. No actual medical secrets or tokens are persisted.

## Sensor adapter and realtime state

`hospitalWardAdapter.js` is the single translation boundary for the nested `hospital_ward_01` payload. UI components consume its stable model. Module availability controls readings:

- HX711 unavailable → bed/load readings unavailable.
- MAX30100 unavailable or invalid → heart rate and SpO₂ are `null`, never valid zeroes.
- PMS5003 unavailable → PM1/PM2.5/PM10 unavailable.
- BH1750 unavailable → lux unavailable.
- MQTT failure → critical transport status.

`useCareGridRealtime` performs the bootstrap fetch, owns one WebSocket, replaces the snapshot for every message, and reconnects with capped exponential backoff. It exposes live/reconnecting/offline, telemetry time, browser receipt time, errors, and retry. A ten-second REST safety refresh runs only while the socket is down. Panic press/release, bed vibration, RFID changes, and MQTT changes become activity-log events; sensor readings are never synthesized.

## Operational workflows

### Ambulance

The five-step workflow captures incident, patient, vitals, capability needs, and the explicit destination decision. Hospital recommendations combine capacity, department, medicine, load, connectivity, distance, and ETA. The user must press `Confirm Hospital`; CareGrid never silently routes. Confirmation reserves a bed through the service boundary and prepares the pre-alert. Pre-alert actions update mission state or call the ambulance service.

### RFID and nursing

The RFID state machine exposes waiting, detected, loading, patient found, unknown, and failure states. Unknown tags require explicit registration. Medication administration requires a matching patient RFID before state changes. Pharmacy collection follows identity → stock selection → dispense → transaction and quantity update.

### Doctor clinical care

Incoming ambulances support acceptance, information request, escalation, bed assignment navigation, and transfer recommendation. Patient actions use action-specific forms for notes, prescriptions, lab orders, diagnosis, transfer, and discharge. Prescriptions query the shared pharmacy service before prescribing.

## Shared modules and future integration

`PharmacyAvailability`, `BedGrid`, `AlertList`, `SystemStatusDrawer`, and common UI primitives are shared rather than copied across roles. Replacing demo operations requires implementing the documented HTTP contracts inside the existing service files; routing, pages, and components should not change. A production authentication implementation can replace `authService` while preserving the `AuthProvider` interface.
