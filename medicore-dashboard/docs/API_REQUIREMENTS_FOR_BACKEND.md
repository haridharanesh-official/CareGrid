# CareGrid backend API requirements

All responses should include an ISO-8601 `updated_at` where operational freshness matters. Production APIs require TLS outside the trusted LAN, authenticated role claims, audit logs for clinical mutations, idempotency keys for ambulance/pharmacy/medication writes, and consistent errors such as `{ "code": "BED_UNAVAILABLE", "message": "..." }`.

## Existing Raspberry Pi gateway APIs (integrated now)

| Method | Route | Request | Response | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/hospital/latest` | — | `{timestamp,nodes:{hospital_ward_01:{node_type,data}}}` | Nurse, Doctor | Latest ward telemetry |
| WS | `/ws/hospital` | — | Repeated replacement snapshots with the same `nodes` envelope | Nurse, Doctor | Realtime ward telemetry |
| GET | `/devices/hospital_ward_01` | — | Legacy real sensor payload; temporary 404 compatibility only | Nurse, Doctor | Latest ward telemetry |
| GET | `/health` | — | Legacy gateway/MQTT state; temporary 404 compatibility only | All authenticated roles | Gateway runtime |

The browser never connects to Mosquitto. MQTT authentication remains on the Raspberry Pi gateway.

## Authentication and authorization

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| POST | `/api/auth/login` | `{username,password,role_context?}` | `{user:{id,name,roles},access_token,expires_at}` | Public | User, Role, Session |
| POST | `/api/auth/logout` | — | `{ok:true}` | All | Session |
| GET | `/api/auth/session` | — | `{user,permissions,expires_at}` | All | User, Role, Permission, Session |

## Patients, RFID, and clinical care

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/patients` | Query `search,ward,status,page` | `{items:[PatientSummary],page,total}` | Nurse, Doctor | Patient, Admission, BedAssignment |
| GET | `/api/patients/:id` | — | `{patient,admission,allergies,conditions,vitals,medications,notes,orders,reports,treatment_plan}` | Nurse read, Doctor read | Patient and clinical entities |
| GET | `/api/patients/by-rfid/:uid` | — | `{patient:null}` or complete permitted patient summary | Nurse, Doctor | RFIDTag, Patient |
| GET | `/api/rfid/resolve/:uid` | — | `{uid,entity_type,entity}` or `404` when unassigned | Nurse, Doctor | RFIDTag, Patient, User, Medicine |
| POST | `/api/patients` | `{name,dob_or_age,gender,blood_group,rfid_uid,contacts?}` | `{patient}` | Nurse registration permission | Patient, RFIDTag, AuditEvent |
| PATCH | `/api/patients/:id` | Allowed demographic/admission fields with version | `{patient}` | Nurse limited, Doctor clinical | Patient, Admission, AuditEvent |
| POST | `/api/patients/:id/clinical-notes` | `{text,category,recorded_at}` | `{clinical_note}` | Doctor | ClinicalNote, AuditEvent |
| POST | `/api/patients/:id/lab-orders` | `{test_code,test_name,priority,notes}` | `{lab_order}` | Doctor | LabOrder, AuditEvent |
| PATCH | `/api/patients/:id/diagnosis` | `{diagnosis,code?,version}` | `{diagnosis}` | Doctor | Diagnosis, AuditEvent |
| POST | `/api/patients/:id/transfers` | `{requested_ward,bed_type,reason,priority}` | `{transfer_request}` | Doctor | TransferRequest, Admission |
| POST | `/api/patients/:id/discharge` | `{plan,follow_up,medications,version}` | `{discharge}` | Doctor | Discharge, Admission, AuditEvent |
| GET | `/api/patients/:id/vitals?from=&to=` | Time window | `{series:[{at,heart_rate,spo2,valid,source}]}` | Nurse, Doctor | VitalObservation |

## Hospitals and recommendation support

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/hospitals` | Query `name,department,lat,lng` | `{items:[Hospital]}` | Ambulance, Doctor | Hospital, Department |
| GET | `/api/hospitals/:id/availability` | Query `department,bed_type,medicine` | `{beds,icu,general,emergency,departments,load,connectivity,updated_at}` | Ambulance, Doctor | CapacitySnapshot, Department |
| POST | `/api/hospitals/recommendations` | `{location,emergency_category,severity,department,bed_type,required_medicines}` | `{recommendations:[{hospital,score,reasons,distance_km,eta_min,availability,reservable}]}` | Ambulance | Hospital, CapacitySnapshot, InventorySnapshot, TravelEstimate |
| POST | `/api/hospitals/:id/incoming-slots` | `{emergency_id,bed_type,ttl_minutes}` | `{reservation_id,status,expires_at}` | Ambulance create, Doctor accept | IncomingSlot, BedReservation |

Recommendation responses must expose reasons and inputs. They must never imply autonomous medical routing.

## Ambulance emergencies and pre-alerts

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/ambulances` | Query `status,hospital_id` | `{items:[AmbulanceMission]}` | Ambulance own, Doctor incoming | Ambulance, EmergencyMission |
| POST | `/api/emergencies` | `{ambulance_id,category,severity,notes,patient,vitals,requirements,location}` | `{emergency}` | Ambulance | EmergencyMission, PatientSnapshot, VitalObservation |
| PATCH | `/api/emergencies/:id` | `{status?,eta?,destination_id?,patient?,vitals?,version}` | `{emergency}` | Ambulance; Doctor status fields | EmergencyMission, AuditEvent |
| POST | `/api/emergencies/:id/pre-alerts` | `{hospital_id,eta,patient_summary,vitals,bed_type,department,medicine_equipment}` | `{pre_alert:{id,delivery_status,delivered_at}}` | Ambulance | PreAlert, Notification, EmergencyMission |
| POST | `/api/emergencies/:id/arrived` | `{arrived_at,handover_to?}` | `{emergency}` | Ambulance | EmergencyMission, Handover |
| POST | `/api/emergencies/:id/decisions` | `{action:accept|request_info|escalate|transfer_recommendation,note}` | `{decision,emergency}` | Doctor | EmergencyDecision, Notification, AuditEvent |

## Beds and wards

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/beds` | Query `ward,type,status` | `{items:[{id,ward,type,occupancy,patient,rfid,sensor_source,cleaning,reservation}]}` | Nurse, Doctor | Bed, Ward, BedAssignment, BedReservation |
| POST | `/api/beds/:id/assign` | `{patient_id,rfid_uid,version}` | `{bed,assignment}` | Nurse, Doctor | BedAssignment, Admission, AuditEvent |
| POST | `/api/beds/:id/reservations` | `{ambulance_id?,patient_id?,expires_at}` | `{reservation}` | Doctor, authorized Ambulance workflow | BedReservation |
| POST | `/api/beds/:id/release` | `{reason,cleaning_required:true,version}` | `{bed}` | Nurse, Doctor | Bed, BedAssignment, CleaningTask |

## Pharmacy and medication

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/pharmacy/inventory` | Query `hospital_id,medicine,status,page` | `{items:[InventoryItem],total}` | Nurse, Doctor | Medicine, InventoryLot, Hospital |
| GET | `/api/pharmacy/search` | Query `q,hospital_id?` | `{items:[{medicine,hospital,available,reserved,status,updated_at,travel_time}]}` | All roles by permission | Medicine, InventorySnapshot, TravelEstimate |
| GET | `/api/pharmacy/cross-hospital` | Query `q,origin_lat,origin_lng` | Same as search, across connected hospitals | Ambulance, Nurse, Doctor | InventorySnapshot, Hospital |
| POST | `/api/pharmacy/reservations` | `{inventory_item_id,quantity,emergency_id?,patient_id?,ttl}` | `{reservation}` | Ambulance critical flow, Nurse, Doctor | MedicineReservation, InventoryLot |
| POST | `/api/pharmacy/dispenses` | `{patient_id,rfid_uid,prescription_id,items:[{inventory_item_id,quantity}]}` | `{transaction,updated_stock}` | Nurse/pharmacy permission | DispenseTransaction, DispenseItem, InventoryLot, AuditEvent |
| GET | `/api/medications/queue` | Query `ward,status,date` | `{items:[MedicationAdministrationDue]}` | Nurse | Prescription, MedicationSchedule, Administration |
| POST | `/api/medications/:scheduleId/administer` | `{patient_id,rfid_uid,administered_at,dose,route,note?}` | `{administration,remaining_schedule}` | Nurse | MedicationAdministration, AuditEvent |
| GET | `/api/prescriptions` | Query `patient_id,status` | `{items:[Prescription]}` | Nurse read, Doctor read | Prescription, PrescriptionItem |
| POST | `/api/prescriptions` | `{patient_id,medicine_id_or_name,dose,frequency,route,duration,instructions,start_date,priority}` | `{prescription,availability}` | Doctor | Prescription, PrescriptionItem, MedicationSchedule, AuditEvent |

## Alerts, tasks, reports, and audit

| Method | Route | Request payload | Response payload | Roles | Entities |
|---|---|---|---|---|---|
| GET | `/api/alerts` | Query `severity,source,acknowledged` | `{items:[Alert]}` | Nurse, Doctor; ambulance mission-scoped | Alert |
| POST | `/api/alerts/:id/acknowledgements` | `{note?}` | `{alert}` | Nurse, Doctor | AlertAcknowledgement, AuditEvent |
| GET | `/api/tasks` | Query `assignee,ward,status,shift` | `{items:[Task]}` | Nurse | Task |
| PATCH | `/api/tasks/:id` | `{status,version}` | `{task}` | Nurse | Task, AuditEvent |
| GET | `/api/reports/clinical` | Query `status,patient_id,date` | `{items:[ClinicalReport]}` | Doctor | ClinicalReport, LabResult |
| POST | `/api/reports/:id/acknowledgements` | `{note?}` | `{report}` | Doctor | ReportAcknowledgement, AuditEvent |
| GET | `/api/reports/clinical/export.csv` | Same filters as current table | CSV stream | Doctor | Report read model |

## Database entities for the next phase

`User`, `Role`, `Permission`, `Session`, `Hospital`, `Department`, `Ward`, `Bed`, `BedAssignment`, `BedReservation`, `CleaningTask`, `Device`, `DeviceTelemetry`, `SensorModule`, `SensorEvent`, `Patient`, `RFIDTag`, `Admission`, `Allergy`, `Condition`, `Diagnosis`, `VitalObservation`, `ClinicalNote`, `TreatmentPlan`, `LabOrder`, `LabResult`, `ClinicalReport`, `Prescription`, `PrescriptionItem`, `MedicationSchedule`, `MedicationAdministration`, `Medicine`, `InventoryLot`, `InventorySnapshot`, `MedicineReservation`, `DispenseTransaction`, `DispenseItem`, `Ambulance`, `EmergencyMission`, `PatientSnapshot`, `TravelEstimate`, `IncomingSlot`, `PreAlert`, `EmergencyDecision`, `Handover`, `Alert`, `AlertAcknowledgement`, `Task`, `Notification`, and immutable `AuditEvent`.
