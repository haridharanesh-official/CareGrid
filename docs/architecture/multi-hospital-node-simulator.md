# Multi-hospital resource node simulator (P0.4)

## Purpose

P0.4 proves that one physical CareGrid ward can coexist with multiple independent hospital resource nodes. The simulator is scalability and integration test infrastructure, not evidence of a real multi-hospital deployment.

```text
hospital_ward_01 physical telemetry (unchanged)
HOSP-002..HOSP-005 simulated resource nodes
                    |
                    v
             authenticated MQTT
                    |
                    v
           FastAPI gateway ingestion
                    |
          transactional SQLite sync
                    |
                    v
       existing P0.2 recommendation engine
                    |
        Ambulance / Nurse / Doctor UI
```

The simulator owns each hospital's local operational state. SQLite stores the latest synchronized snapshot. The recommendation service never reads simulator memory or MQTT directly; it continues to query the repository and database.

## Physical and simulated nodes

`hospital_ward_01` remains the physical `smart_hospital_ward` device and keeps its existing topics under `caregrid/hospital/ward/ward-01/...`. It represents individual ward sensors and is not replaced by the simulator.

The four `simulated_hospital` nodes represent hospital-level operational resources:

- `HOSP-002` — PSG Hospitals
- `HOSP-003` — KMCH
- `HOSP-004` — Sri Ramakrishna Hospital
- `HOSP-005` — Government Medical College Hospital

`HOSP-001` remains the physical/demo database hospital and is not claimed as a simulated resource node.

## MQTT topics

```text
caregrid/hospital/nodes/{hospital_id}/resources
caregrid/hospital/nodes/{hospital_id}/status
```

Both use QoS 1 and retained snapshots. A retained `online=true` value is advisory only: payload time, not receipt time, drives freshness.

## Resource schema and validation

Resource messages contain `hospital_id`, `node_type`, positive `sequence`, ISO-8601 `timestamp`, capability flags, and `resources` for beds, departments, equipment, and pharmacy. Ingestion rejects:

- unknown or malformed hospital IDs;
- a hospital ID that differs from the MQTT topic;
- negative counts or non-integer counts;
- occupied plus reserved beds above total;
- bed `available` that differs from `total - occupied - reserved`;
- equipment available plus reserved above total;
- pharmacy reserved above total or contradictory available quantity;
- malformed timestamps, types, or missing resource groups;
- timestamps more than 60 seconds in the future, preventing a forged clock value from remaining LIVE indefinitely.

One SQLite transaction updates the node metadata and normalized `bed_capacity`, `departments`, `equipment_inventory`, `pharmacy_inventory`, and `hospitals` records. A failed validation or write rolls back the entire update. Existing rows not represented by the compact simulator snapshot remain intact.

## Liveness

Hospital resource-node freshness mirrors ward timing while remaining a separate state model:

```text
age <= 15 seconds       LIVE
15 < age <= 30 seconds  STALE
age > 30 seconds        OFFLINE
```

`last_seen` comes from a valid resource or status payload timestamp. Graceful `online=false` immediately makes the node OFFLINE. `last_seen`, `age_seconds`, `connection_status`, the advertised state, resource version, and status sequence are exposed by `GET /api/hospital-nodes`. The snapshot is retained for audit even when the node becomes stale or offline.

Recommendation behavior is explicit:

- `LIVE`: normal eligibility and scoring.
- `STALE`: remains eligible with `HOSPITAL_RESOURCE_NODE_STALE`, a visible warning, and a 15-point readiness penalty.
- `OFFLINE`: hard rejected with `HOSPITAL_RESOURCE_NODE_OFFLINE`.
- no registered resource node: existing database snapshot behavior remains available as `DATABASE_SNAPSHOT` (including `HOSP-001`).

## Ordering and replay protection

The gateway tracks `resource_version` per hospital. A resource update is applied only when its positive sequence is greater than the stored version. Older and duplicate retained messages are ignored. Status messages have an independent monotonically increasing sequence because status and resource messages are separate streams.

Simulator sequences begin with an epoch-millisecond value so a restarted simulator normally advances beyond a previous process. Real gateways should persist their counter across restarts.

## Deterministic scenarios

The simulator never uses random changes by default. It supports:

```text
NORMAL
HIGH_LOAD
ICU_FULL
EMERGENCY_BEDS_FULL
ADRENALINE_LOW
ADRENALINE_OUT
VENTILATOR_OUT
CARDIOLOGY_UNAVAILABLE
NODE_OFFLINE
RECOVERY
```

Each scenario is a complete deterministic snapshot derived from that hospital's baseline. `RECOVERY` restores the baseline.

## CLI

From `raspberry-pi/simulator`:

```powershell
python multi_hospital_simulator.py --hospital HOSP-002 --scenario NORMAL
python multi_hospital_simulator.py --hospital HOSP-002 --scenario CARDIOLOGY_UNAVAILABLE
python multi_hospital_simulator.py --hospital HOSP-002 --scenario RECOVERY
python multi_hospital_simulator.py --all --scenario HIGH_LOAD
```

One process manages all four nodes with one MQTT client. Configuration comes from `CAREGRID_MQTT_HOST`, `CAREGRID_MQTT_PORT`, `CAREGRID_MQTT_USERNAME`, `CAREGRID_MQTT_PASSWORD`, and `CAREGRID_SIMULATOR_PUBLISH_INTERVAL`. Ctrl+C publishes `online=false` before disconnecting when the broker is reachable.

## API and frontend

`GET /api/hospital-nodes` returns node identity, name, node type, current connection status, timestamps, age, and versions. `GET /api/hospital-nodes/{hospital_id}` also includes the current synchronized resource snapshot.

The Hospital Finder shows the resource source without adding a new dashboard. Browser code continues to use REST/WebSocket APIs and never connects directly to MQTT.

## Security and limitations

MQTT authentication uses environment configuration and no credentials are stored in source. Unknown hospital IDs cannot create hospitals. P0.4 uses plaintext MQTT when the configured broker does; production deployments should add broker TLS, per-node credentials, topic ACLs, signed provisioning, and durable node counters.

The simulator does not prove hospital network reliability, hardware behavior, clinical correctness, or real operational deployment. A future hospital gateway can replace a simulated node by publishing the same validated resource and status contract; no recommendation-engine rewrite is required.
