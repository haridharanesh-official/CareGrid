import { caregridRequest } from "./caregridApi.js";

const normalizeCase = item => ({
  ...item,
  id: item.id,
  patient: item.patient || "Unknown patient",
  name: item.patient || "Unknown patient",
  type: item.incident_type,
  category: item.incident_type,
  department: item.requested_department || "Emergency",
  bed: item.requested_bed || "Emergency",
  bedType: item.requested_bed || "Emergency",
  hospitalId: item.hospital_id,
  eta: item.eta_minutes ?? 8,
  vitals: { heartRate: item.heart_rate, spo2: item.spo2 },
});

export async function getAmbulances() {
  const response = await caregridRequest("/api/emergency-cases");
  return (response.items || []).map(normalizeCase);
}

export async function createEmergency(input) {
  const response = await caregridRequest("/api/emergency-cases", {
    method: "POST",
    body: JSON.stringify(input),
  });
  return { ...input, ...normalizeCase(response), name: input.name || response.patient, destination: input.destination || response.destination };
}

export async function updateEmergency(id, input) {
  const response = await caregridRequest(`/api/emergency-cases/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  return normalizeCase(response);
}

export async function sendHospitalPreAlert(input) {
  return caregridRequest("/api/prealerts", {
    method: "POST",
    body: JSON.stringify({ ...input, caseId: input.caseId || input.ambulanceId }),
  });
}

export async function markAmbulanceArrived(id) {
  return updateEmergency(id, { status: "Arrived" });
}
