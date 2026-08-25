# CareGrid frontend interaction audit

The table covers every visible action family. Repeated row actions use the same implementation for each record. `Tested` is updated during automated/build/browser verification.

| Page | Control | Expected action | Implemented action | Backend dependency | Tested |
|---|---|---|---|---|---|
| Login | Role cards | Select operational portal | Sets isolated role selection | Auth later | Build |
| Login | Continue to CareGrid | Create session and route | Calls `authService.login`, navigates to role dashboard | Auth later | Browser |
| All portals | CareGrid status | Inspect connection | Opens system status drawer | Live gateway | Browser |
| All portals | Retry | Refresh gateway | Calls shared live refresh | Live gateway | Build |
| All portals | Navigation | Open real page | React Router navigation | None | Browser |
| All portals | Sign out | End session | Calls auth logout and routes to login | Auth later | Browser |
| Demo layout | Role switcher | Change demo role | Replaces demo session and routes | Demo only | Browser |
| Ambulance dashboard | Start Emergency | Begin mission | Navigates to five-step form | None | Browser |
| Ambulance dashboard | Open mission/pre-alert | Resume mission | Navigates to current pre-alert | None | Browser |
| Emergency steps 1–3 | Back / Continue | Move through validated capture | Updates local step/form state | None | Browser |
| Emergency step 3 | Find suitable hospitals | Request recommendation | Calls `recommendHospital` with needs | Hospital API later | Browser |
| Emergency step 4 | Confirm Hospital | Select explicit destination | Stores selected alternative; no auto-route | None | Browser |
| Emergency step 5 | Confirm Hospital | Reserve and create mission | Calls hospital reserve and ambulance create | Hospital/Ambulance APIs | Browser |
| Hospital Finder | Name/filter/sort controls | Refine candidates | Filters/sorts current hospital dataset | Hospital API later | Browser |
| Hospital Finder | Hospital selection | Start explicit selection flow | Opens emergency workflow | None | Build |
| Hospital Finder | Medicine search | Query hospital stock | Calls shared pharmacy search | Pharmacy API later | Browser |
| Patient in transit | Update/start | Edit mission patient | Opens emergency workflow | None | Build |
| Pre-alert | Send Pre-Alert | Deliver handover | Calls `sendHospitalPreAlert`, records delivery | Ambulance API later | Browser |
| Pre-alert | Update ETA | Update receiving team | Calls emergency update, decrements demo ETA | Ambulance API later | Browser |
| Pre-alert | Change Hospital | Reconsider destination | Opens hospital finder | None | Build |
| Pre-alert | Mark Arrived | Complete transport | Calls `markAmbulanceArrived` | Ambulance API later | Browser |
| Pre-alert | Cancel Emergency | Clear mission | Clears shared emergency and pre-alert | Ambulance API later | Browser |
| History | Mission records | Inspect recent missions | Renders ambulance service data | Ambulance API later | Build |
| Nurse live ward | Refresh telemetry | Retry live APIs | Calls shared refresh | Live gateway | Browser |
| Connected wards | Open live ward / View beds | Navigate to detail | Opens implemented live or bed page | None | Build |
| Nurse beds | Manage | Inspect bed state | Opens action-specific bed modal | Bed API later | Browser |
| Nurse beds | Release / confirm | Change bed workflow state | Calls `releaseBed` or confirms availability | Bed API later | Browser |
| Nurse patients | Scan/Open via RFID | Open identity workflow | Routes with patient RFID | Patient API later | Build |
| RFID | Scan RFID | Run state machine and lookup | Calls `getPatientByRfid` after detected/loading states | Patient API later | Browser |
| RFID | Use demo tag | Demonstrate known identity | Runs lookup for fictional UID | Demo only | Browser |
| RFID unknown | Register Patient | Open deliberate mapping form | Opens registration form | Patient API later | Browser |
| RFID register | Register and map | Create patient/tag mapping | Calls `registerPatient` | Patient API later | Browser |
| RFID patient | Open medication queue | Continue care workflow | Navigates to medications | None | Build |
| Medications | Administer | Start identity confirmation | Opens medication confirmation modal | None | Browser |
| Medications | Scan demo tag | Populate matching RFID | Sets UID for explicit confirmation | RFID backend later | Browser |
| Medications | Confirm administration | Record dose | Calls `administerMedication`; enforces matching RFID | Medication API later | Browser |
| Nurse pharmacy | Scan patient RFID | Identify collector | Calls patient RFID lookup | Patient API later | Browser |
| Nurse pharmacy | Search/select stock | Verify medicine | Calls shared pharmacy search and selects row | Pharmacy API later | Browser |
| Nurse pharmacy | Dispense & record | Reduce stock and transact | Calls `dispenseMedicine` | Pharmacy API later | Browser |
| Tasks | Task checkboxes | Complete/reopen task | Updates task state | Task API later | Browser |
| Alerts | Acknowledge | Record review | Updates shared alert acknowledgement | Alert API later | Browser |
| Doctor dashboard | Command/patient links | Open operational detail | Navigates to emergencies or patient | None | Build |
| Emergencies | Accept | Accept incoming ambulance | Confirmation then emergency status update | Ambulance API later | Browser |
| Emergencies | Request information | Request handover update | Confirmation and status update | Ambulance API later | Browser |
| Emergencies | Assign bed | Open bed command | Navigates to doctor beds | None | Browser |
| Emergencies | Escalate | Notify emergency lead | Confirmation and status update | Ambulance API later | Browser |
| Emergencies | Redirect | Recommend transfer only | Confirmation and status update; no autonomous routing | Hospital/Ambulance APIs | Browser |
| Doctor patients | Search | Filter records | Filters by name/UHID/RFID | Patient API later | Browser |
| Doctor patients | View Patient | Open clinical record | Routes to `/doctor/patient/:id` | Patient API later | Browser |
| Patient detail | Add Clinical Note | Save note form | Calls `createClinicalNote` | Clinical API later | Browser |
| Patient detail | Prescribe Medicine | Save prescription form | Calls `createPrescription` | Medication API later | Browser |
| Patient detail | Order Lab | Save lab form | Calls `createLabOrder` | Lab API later | Browser |
| Patient detail | Update Diagnosis | Persist diagnosis | Calls `updatePatient` and updates view | Patient API later | Browser |
| Patient detail | Request Transfer | Create transfer request | Calls `updatePatient` service boundary | Transfer API later | Browser |
| Patient detail | Discharge Patient | Create discharge plan | Calls `updatePatient` service boundary | Discharge API later | Browser |
| Prescriptions | Check availability | Search medicine stock | Calls `searchMedicine`, renders explicit stock state | Pharmacy API later | Browser |
| Prescriptions | New prescription | Open proper form | Opens prescription modal | None | Browser |
| Prescriptions | Create prescription | Save active order | Calls `createPrescription` | Medication API later | Browser |
| Orders | Mark reviewed | Acknowledge report | Changes row status to Reviewed | Lab API later | Browser |
| Doctor beds | Assign/reserve | Inspect selected bed | Opens selected bed modal | Bed API later | Browser |
| Doctor beds | Reserve for ambulance | Reserve free bed | Calls `reserveBed` | Bed API later | Browser |
| Doctor pharmacy | Search | Cross-hospital availability | Calls shared pharmacy service | Pharmacy API later | Browser |
| Reports | Export displayed data | Download current rows | Generates CSV Blob and triggers download | None | Build |
| Reports | Review/acknowledge/handover | Update report workflow | Shows action-specific state confirmation | Report API later | Browser |
