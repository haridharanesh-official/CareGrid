const normalizeUid = value => String(value || "").trim().toUpperCase();

export const DEMO_PATIENTS = [
  { patient_id:"PATIENT-001", name:"Balaji", blood_group:"O+", allergies:"none recorded", condition:null, rfid_uid:"D0:DA:F6:5F", demo_data:true },
  { patient_id:"PATIENT-002", name:"Akshitha", blood_group:"B+", allergies:"none recorded", condition:null, rfid_uid:"1D:69:50:06", demo_data:true },
  { patient_id:"PATIENT-003", name:"Lekha", blood_group:"A+", allergies:"none recorded", condition:"Smile disorder", rfid_uid:"53:67:70:56", demo_data:true },
];

export const DEMO_DOCTORS = [
  { doctor_id:"DOC-001", name:"Hari", department:"Emergency Medicine", rfid_uid:"AA:B4:32:06", demo_data:true },
];

export const RESERVED_RFID_UIDS = ["04:06:96:04", "76:4D:32:06", "43:E7:50:06"];

export const findDemoPatientByUid = uid => DEMO_PATIENTS.find(item => item.rfid_uid === normalizeUid(uid)) || null;
export const findDemoPatientById = id => DEMO_PATIENTS.find(item => item.patient_id === String(id || "").trim().toUpperCase()) || null;
export const findDemoDoctorByUid = uid => DEMO_DOCTORS.find(item => item.rfid_uid === normalizeUid(uid)) || null;

export function getDemoRfidResult(uid) {
  const normalized = normalizeUid(uid);
  const patient = findDemoPatientByUid(normalized);
  const doctor = findDemoDoctorByUid(normalized);
  const entity = patient || doctor;
  const entityType = patient ? "patient" : doctor ? "doctor" : null;
  if (entity) return { found:true, known:true, reserved:false, uid:normalized, type:entityType, entity_type:entityType, entity_id:patient?.patient_id || doctor?.doctor_id, record:entity, entity, status:"RFID verified", demo_data:true, offline_fallback:true };
  if (RESERVED_RFID_UIDS.includes(normalized)) return { found:false, known:false, reserved:true, uid:normalized, status:"Reserved RFID Tag", demo_data:true, offline_fallback:true };
  return { found:false, known:false, reserved:false, uid:normalized, status:"Unknown RFID Tag", demo_data:true, offline_fallback:true };
}

export { normalizeUid };
