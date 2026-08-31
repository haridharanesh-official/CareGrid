# Multi-Hospital Node Simulator

This deterministic simulator represents `HOSP-002` through `HOSP-005` as independent hospital resource nodes. It publishes resource snapshots and liveness separately from the physical `hospital_ward_01` telemetry path.

```powershell
python multi_hospital_simulator.py --hospital HOSP-002 --scenario NORMAL
python multi_hospital_simulator.py --hospital HOSP-003 --scenario ICU_FULL
python multi_hospital_simulator.py --all --scenario ADRENALINE_OUT
```

Configuration uses `CAREGRID_MQTT_HOST`, `CAREGRID_MQTT_PORT`, `CAREGRID_MQTT_USERNAME`, `CAREGRID_MQTT_PASSWORD`, and `CAREGRID_SIMULATOR_PUBLISH_INTERVAL`. No broker credentials are stored in source. Stop with Ctrl+C; the simulator publishes `online=false` for every managed node before disconnecting when possible.

Supported scenarios are `NORMAL`, `HIGH_LOAD`, `ICU_FULL`, `EMERGENCY_BEDS_FULL`, `ADRENALINE_LOW`, `ADRENALINE_OUT`, `VENTILATOR_OUT`, `CARDIOLOGY_UNAVAILABLE`, `NODE_OFFLINE`, and `RECOVERY`.
