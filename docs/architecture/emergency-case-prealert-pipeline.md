# Emergency case and hospital pre-alert pipeline

P0.3 turns an ambulance handover into a persistent, auditable workflow.

## Lifecycle

Cases are created as `CREATED`, then move through `HOSPITAL_RECOMMENDED`, `DESTINATION_CONFIRMED`, `PREALERT_SENT`, `ACKNOWLEDGED`, `ARRIVED`, and `CLOSED`. The backend owns the readable `CG-EMR-YYYY-NNNNNN` case number and validates transitions.

`POST /api/emergency-cases` stores the incident, patient context, nullable vitals, requirements, and ambulance location. Known RFID UIDs resolve to existing patient records; unknown UIDs remain unresolved and never create an identity.

## Recommendations and pre-alerts

`POST /api/emergency-cases/{id}/recommend` delegates to the P0.2 resource-aware engine and stores the complete response, criteria, score breakdown, resource availability, reason, and generation time as a recommendation snapshot. `POST /api/emergency-cases/{id}/confirm-destination` accepts only an eligible stored recommendation. In one SQLite transaction it records the operator confirmation and creates one `SENT` hospital pre-alert with a dispatch-time snapshot of patient, incident, nullable vitals, requirements, and destination.

Nurses use `GET /api/prealerts` and `POST /api/prealerts/{id}/acknowledge`; doctors consume the same incoming case/pre-alert view. Pharmacy displays required medicines informationally. P0.3 does not reserve or decrement beds, pharmacy stock, or equipment.

## Realtime and limitations

The existing `/ws/hospital` stream continues sending telemetry and now also emits structured `emergency_case_created`, `recommendation_generated`, `destination_confirmed`, `prealert_created`, `prealert_acknowledged`, `emergency_arrived`, and `emergency_closed` events. The frontend keeps gateway/ward liveness derived from real telemetry; workflow records are demo/simulation records and do not claim delivery to an external hospital network.

Repeated destination confirmation and acknowledgement are idempotent. Arrival and close are intentionally minimal P0.3 transitions; admission, reservation, dispensing, and external notification delivery remain later milestones.
