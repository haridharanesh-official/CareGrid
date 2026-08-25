# CAREGRID Literature Review

## 1. Introduction

CAREGRID is a smart hospital and ward coordination platform that combines sensor-based monitoring, local edge processing, role-based dashboards and emergency coordination.

The purpose of this literature review is to understand existing approaches in:

- Healthcare IoT
- Edge computing in healthcare
- Smart hospital monitoring
- Fall detection
- IV monitoring
- Patient safety
- Emergency hospital capacity management
- RFID-based patient identification
- Medication safety and workflow

The literature review is used to guide technology selection and system architecture rather than to claim that CAREGRID has invented the individual technologies.

---

## 2. Healthcare IoT and Smart Hospitals

### Research focus

Healthcare IoT systems use connected sensors and communication technologies to monitor patients, environments and hospital resources.

The main concepts relevant to CAREGRID are:

- Distributed sensor nodes
- Continuous monitoring
- Gateway-based communication
- Real-time dashboards
- Event-based alerts
- Integration of multiple sources of information

### Relevance to CAREGRID

The literature supports the use of a distributed sensing architecture in which different sensors collect information and a gateway provides a common communication path.

CAREGRID applies this concept through:

Sensor Nodes
→ Raspberry Pi Gateway
→ MQTT
→ CAREGRID dashboards

### Design decision

The research supports keeping the sensing layer modular so that additional beds or sensors can be added without redesigning the entire system.

---

## 3. Edge Computing in Healthcare

### Research focus

Edge computing places computation closer to where data is generated instead of sending every event to a remote cloud service.

Relevant advantages include:

- Lower communication delay
- Local processing
- Reduced dependence on internet connectivity
- Potential privacy benefits
- Distributed processing

### Relevance to CAREGRID

CAREGRID uses a Raspberry Pi as a local gateway/edge component.

The gateway receives sensor data and provides the local path for:

- Sensor telemetry
- MQTT communication
- Dashboard updates
- Local operational status

### Design decision

The project follows an edge-first direction for the critical local monitoring path.

Cloud or external connectivity can be considered later for:

- Higher-level analytics
- Synchronization
- Multi-hospital coordination
- Long-term data analysis

### Limitation

The current prototype should not be described as fully autonomous or clinically validated edge AI.

The current objective is to demonstrate reliable sensing, gateway connectivity and operational dashboards.

---

## 4. Fall Detection and Privacy-Preserving Monitoring

### Research focus

Fall detection research includes camera-based, wearable, infrared, radar and mmWave approaches.

An important consideration in hospital environments is patient privacy.

### Relevance to CAREGRID

CAREGRID investigates mmWave/radar-based sensing as a privacy-conscious alternative to continuous camera monitoring.

The objective is to detect relevant movement or fall-risk events without relying on continuous visual recording.

### Design decision

The fall/emergency sensing layer is designed as:

mmWave / emergency input
→ Edge processing
→ Event
→ Dashboard / response workflow

### Limitation

Fall detection performance must be validated experimentally.

CAREGRID should not claim 100% fall detection accuracy without a sufficient test dataset.

---

## 5. IV Monitoring

### Research focus

Automated IV monitoring approaches include:

- Flow sensors
- Optical sensing
- Pressure sensing
- Weight-based monitoring

Weight-based monitoring is attractive for a prototype because remaining fluid can be estimated from the change in IV bag weight.

### Relevance to CAREGRID

CAREGRID uses:

Load Cell
→ HX711
→ Weight measurement
→ Threshold/event detection
→ Dashboard

### Design decision

The prototype uses weight-based IV monitoring because it is simple to demonstrate, modular and does not require modification of the fluid pathway.

### Future work

The system requires:

- Calibration
- Different bag/container testing
- Disturbance testing
- Threshold validation
- False-alert measurement

before any clinical deployment claim.

---

## 6. Patient Safety

Patient safety is a major motivation for CAREGRID.

The World Health Organization reports that around 1 in 10 patients is harmed in healthcare and that more than 3 million deaths occur annually due to unsafe care. WHO also identifies falls and patient misidentification among common adverse events that can contribute to preventable harm. [WHO Patient Safety]

### CAREGRID relevance

The project focuses on operational monitoring and response for events such as:

- Bed-exit events
- IV-low conditions
- Emergency/SOS events
- Fall-related events
- Nurse-call events

The objective is not autonomous medical diagnosis.

The objective is faster awareness, organized response and better operational coordination.

---

## 7. Emergency Hospital Capacity

### Research focus

Emergency response is affected not only by detecting a patient emergency but also by knowing whether a receiving facility can handle the patient.

Relevant information may include:

- Available beds
- ICU availability
- Emergency readiness
- Hospital capability
- Data freshness
- Travel distance

### Relevance to CAREGRID

The original CAREGRID concept extends beyond ward monitoring toward emergency hospital capacity coordination.

The proposed workflow is:

Emergency
→ Check suitable facility
→ Compare availability/capability
→ Support ambulance decision
→ Record the response

### Design decision

The capacity layer is intended to provide decision support rather than independently make a clinical destination decision.

Clinical staff remain responsible for the final decision.

---

## 8. RFID-Based Patient Identification

### Research focus

RFID can be used to associate a physical patient or bed with a digital identity.

Potential advantages include:

- Faster identification
- Reduced manual lookup
- Linking physical and digital workflows
- Supporting medication and care workflows

### CAREGRID relevance

CAREGRID includes an RFID identity bridge in its development direction.

The intended architecture is:

RFID Identifier
→ Secure Patient Record
→ Authorized Dashboard

### Security principle

Sensitive medical information should not be stored directly on the RFID tag.

The RFID identifier should be used to retrieve authorized information from a secure backend.

---

## 9. Medication Safety

The WHO Medication Without Harm initiative identifies medication errors as a major source of avoidable harm and estimates the global cost associated with medication errors at approximately US$42 billion annually.

### CAREGRID future relevance

A future CAREGRID extension can provide nurses with:

- Patient identity
- Prescribed medication
- Dose
- Scheduled time
- Medication status/reminder

### Important safety boundary

CAREGRID should not independently:

- Prescribe medication
- Change dosage
- Change treatment plans
- Make autonomous clinical decisions

The prescription should come from an authorized healthcare system or healthcare professional.

CAREGRID would support the workflow by displaying authorized information and reminders.

---

## 10. Research-to-Design Mapping

| Research Area | Finding / Design Insight | CAREGRID Decision |
|---|---|---|
| Healthcare IoT | Distributed sensing is suitable for connected monitoring | Modular sensor nodes |
| Edge computing | Local processing can reduce dependence on remote services | Raspberry Pi gateway |
| Smart hospitals | Multiple devices need a common monitoring layer | Unified dashboard |
| Fall detection | Privacy matters in patient environments | Explore mmWave sensing |
| IV monitoring | Fluid level can be estimated from weight | Load cell + HX711 |
| Patient safety | Preventable harm makes timely monitoring important | Event monitoring and workflow |
| Emergency capacity | Facility capacity matters during emergency routing | Capacity-routing roadmap |
| RFID | Digital identity can connect physical patient and record | RFID identity bridge |
| Medication safety | Correct patient/dose/time matters | Future medication workflow |

---

## 11. Current Prototype vs Future Research

### Current prototype

The current CAREGRID implementation focuses on:

- Sensor data acquisition
- Raspberry Pi gateway
- MQTT communication
- Live telemetry
- Sensor/node status
- Role-based dashboards
- RFID identity bridge

### Future research

Future work includes:

- More robust fall detection
- Alert prioritization and escalation
- Hospital bed-capacity coordination
- Ambulance-to-hospital routing
- Secure patient-record integration
- RFID patient mapping
- Medication schedule/reminder workflow
- Clinical validation
- Hospital-system interoperability

---

## 12. Conclusion

The literature review shows that CAREGRID is built by combining established research directions rather than claiming individual sensing technologies as novel.

The research contribution is the mapping of these technologies into a common hospital coordination architecture:

Sense
→ Connect
→ Process
→ Display
→ Respond
→ Future escalation and coordination

The next research stage is experimental validation of sensing accuracy, latency, reliability, usability and safety boundaries.