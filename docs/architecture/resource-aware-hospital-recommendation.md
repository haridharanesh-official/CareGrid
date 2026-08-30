# Resource-aware hospital recommendation (P0.2)

CareGrid P0.2 replaces prepared frontend ranking with a deterministic backend decision pipeline:

```text
Emergency requirements -> hard eligibility -> SQLite resources -> distance -> weighted score -> explanation
```

`GET /api/hospitals/recommend` evaluates all P0.1 hospitals. Hospital status, requested department, requested bed capacity, required medicine, ICU requirements and emergency capability are hard eligibility gates. Ineligible hospitals are returned under `rejected` with explicit `rejection_reasons`; they are never selectable.

Eligible hospitals are ranked by a documented 100-point model: distance 35, requested-bed capacity 25, ICU readiness 15, medicine availability 10, department capability 10 and emergency readiness 5. Responses include `score_breakdown`, distance, estimated travel time, resource evidence and a human-readable reason. `recommended` is the highest-ranked eligible hospital and `items` contains eligible alternatives in rank order.

Ambulance GPS coordinates should be supplied as a latitude/longitude pair. When absent, the simulation uses a clearly identified Coimbatore demo origin. Hospital capacities remain database-backed simulation records; gateway and ward liveness continue to come only from realtime telemetry.

The frontend still calls the real API first. Its existing centralized mock data is used only for the established offline, timeout, 404 and 5xx fallback conditions.
