# CareGrid multi-hospital resource database

## Purpose

P0.1 moves hospital availability, departments, bed capacity, equipment and pharmacy stock into a backend-owned SQLite model. These records support prototype and simulation workflows only; they do not represent the named hospitals' current operational availability.

## Architecture and data flow

```text
CareGrid frontend -> FastAPI REST API -> hospital repository -> SQLite
                         |
                         +-> existing MQTT/WebSocket ward gateway (unchanged)
```

The browser attempts the real FastAPI API first. The existing centralized frontend data in `demoHospitalData.js` remains an offline resilience fallback only for timeouts, network failures, 404 responses and 5xx responses. It is not used for 400, 401 or 403 responses. Database resource data never determines Gateway or ward LIVE status; realtime telemetry remains authoritative for liveness.

## Schema

- `hospitals`: identity, location, operational flags and simulation marker.
- `departments`: per-hospital service status and doctors on duty.
- `bed_capacity`: total, occupied and reserved capacity by bed type. Available beds are computed as `total - occupied - reserved`.
- `equipment_inventory`: total, available, reserved and operational equipment state.
- `pharmacy_inventory`: total and reserved stock. Available stock is computed as `total_quantity - reserved_quantity`.
- `hospital_resources`: compact critical and facility capabilities.

SQLite foreign keys are enabled for every repository connection. Checks reject negative quantities and inconsistent capacity. Seed writes are idempotent upserts keyed by hospital and resource identity.

## Prototype seed

Five records are seeded with `is_demo = 1`: Ganga Hospital, PSG Hospitals, KMCH, Sri Ramakrishna Hospital and Government Medical College Hospital. Each receives a deliberately different simulation profile for departments, beds, equipment and the 15 supported medicines.

## APIs

- `GET /api/hospitals`
- `GET /api/hospitals/{hospital_id}`
- `GET /api/hospitals/{hospital_id}/departments`
- `GET /api/hospitals/{hospital_id}/beds`
- `GET /api/hospitals/{hospital_id}/equipment`
- `GET /api/hospitals/{hospital_id}/pharmacy`
- `GET /api/hospitals/{hospital_id}/resources`
- `GET /api/pharmacy/search?query=<medicine>` (`q` remains a compatibility alias)

Successful resource responses identify `source: database` and `simulation: true`. Pharmacy result fields retain the frontend-compatible names `hospital_id`, `hospital`, `medicine`, `available`, `reserved`, `status` and `updated`.

## Preparing for P0.2

The repository exposes normalized hospital, department, bed, equipment, pharmacy and aggregate resource reads. P0.2 can build the resource-aware emergency recommendation engine on these functions without changing storage or frontend fallback behavior.
