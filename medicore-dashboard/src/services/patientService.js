import { caregridRequest, CareGridApiError } from "./caregridApi.js";

const normalizePatient = item => {
  const allergies = !item.allergies || item.allergies.toLowerCase() === "none recorded" ? [] : [item.allergies];
  return {
    ...item,
    id: item.patient_id,
    uhid: item.patient_id,
    rfid: item.rfid_uid || "Unassigned",
    age: "Unavailable",
    gender: "Unavailable",
    blood: item.blood_group || "Unavailable",
    allergies,
    conditions: item.condition ? [item.condition] : [],
    diagnosis: item.condition || "No demo condition recorded",
    bed: "Unassigned",
    ward: "Hospital demo registry",
    doctor: "Dr. Hari",
    medications: [],
    instructions: "No nursing instruction recorded.",
    vitals: { heartRate: null, spo2: null },
    demoData: Boolean(item.demo_data),
  };
};

export async function getPatients() {
  const response = await caregridRequest("/api/patients");
  return (response.items || []).map(normalizePatient);
}

export async function getPatient(id) {
  return normalizePatient(await caregridRequest(`/api/patients/${encodeURIComponent(id)}`));
}

export async function getPatientByRfid(uid) {
  try {
    const response = await caregridRequest(`/api/rfid/${encodeURIComponent(uid)}`);
    return response.known && response.entity_type === "patient"
      ? normalizePatient({ ...response.entity, rfid_uid: response.uid, demo_data: response.demo_data })
      : null;
  } catch (error) {
    if (error instanceof CareGridApiError && error.status === 404) return null;
    throw error;
  }
}

export async function registerPatient() {
  throw new Error("Patient registration is not enabled in this demo backend");
}

export async function updatePatient(id, input) {
  const response = await caregridRequest(`/api/patients/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return normalizePatient(response);
}

export async function createClinicalNote(id, note) {
  return caregridRequest(`/api/patients/${encodeURIComponent(id)}/events`, {
    method: "POST",
    body: JSON.stringify({ event_type: "clinical_note", severity: "info", summary: note.text, payload: note }),
  });
}

export async function createLabOrder(id, order) {
  return caregridRequest(`/api/patients/${encodeURIComponent(id)}/events`, {
    method: "POST",
    body: JSON.stringify({ event_type: "lab_order", severity: order.priority || "routine", summary: `Lab ordered: ${order.test}`, payload: order }),
  });
}
