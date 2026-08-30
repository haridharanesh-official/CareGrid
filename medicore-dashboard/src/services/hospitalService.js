import { caregridRequest, shouldUseDemoFallback } from "./caregridApi.js";
import { getHospitalFallbackData } from "../data/demoHospitalData.js";

const normalizeRecommendation = item => {
  const hospital = item.hospital || item;
  const distance = Number(item.distance ?? 0);
  const medicineQuantity = item.availability?.medicine_quantity;
  const rejected = item.eligibility === "rejected";
  return {
    ...hospital,
    id: hospital.id,
    name: hospital.name,
    score: Number(item.score ?? 0),
    distance,
    eta: Number(item.eta_minutes ?? item.eta ?? Math.max(3, Math.round(distance * 3 + 4))),
    emergencyBeds: hospital.emergency_beds_available ?? 0,
    icuBeds: hospital.icu_beds_available ?? 0,
    normalBeds: hospital.normal_beds_available ?? 0,
    connected: hospital.status === "online",
    medicine: medicineQuantity == null ? true : medicineQuantity > 0,
    reservable: item.eligibility ? !rejected : hospital.status === "online",
    reason: item.reason || "Operational CareGrid demo hospital.",
    availability: item.availability || {},
    department: item.availability?.requested_department_name,
    departmentAvailable: item.availability?.requested_department,
    medicineName: item.availability?.medicine,
    ventilators: item.availability?.ventilators,
    rejectionReasons: item.rejection_reasons || [],
    scoreBreakdown: item.score_breakdown || {},
    eligibility: item.eligibility || "eligible",
    status: rejected ? "NOT ELIGIBLE" : hospital.status,
    demoData: Boolean(item.offline_fallback || hospital.offline_fallback),
    simulationData: Boolean(hospital.simulation || hospital.is_demo || hospital.demo_data),
  };
};

export async function getHospitals() {
  try {
    const response = await caregridRequest("/api/hospitals", { timeoutMs: 2500 });
    return (response.hospitals || response.items || []).map(normalizeRecommendation).sort((a, b) => b.score - a.score);
  } catch (error) {
    if (!shouldUseDemoFallback(error)) throw error;
    return getHospitalFallbackData();
  }
}

export async function getHospitalAvailability(id) {
  return caregridRequest(`/api/hospitals/${encodeURIComponent(id)}`);
}

export async function recommendHospital(criteria = {}) {
  const params = new URLSearchParams();
  if (criteria.department) params.set("department", criteria.department);
  if (criteria.bedType || criteria.requestedBed) params.set("requested_bed", criteria.bedType || criteria.requestedBed);
  if (criteria.medicine) params.set("medicine", criteria.medicine);
  if (criteria.icu) params.set("icu_required", "true");
  params.set("emergency_required", String(criteria.emergencyRequired ?? true));
  if (criteria.latitude != null) params.set("latitude", String(criteria.latitude));
  if (criteria.longitude != null) params.set("longitude", String(criteria.longitude));
  try {
    const response = await caregridRequest(`/api/hospitals/recommend?${params}`, { timeoutMs: 2500 });
    const eligible = (response.items || response.recommendations || []).map(normalizeRecommendation).sort((a, b) => b.score - a.score);
    const rejected = (response.rejected || []).map(normalizeRecommendation).sort((a, b) => a.distance - b.distance);
    return [...eligible, ...rejected];
  } catch (error) {
    if (!shouldUseDemoFallback(error)) throw error;
    return getHospitalFallbackData(criteria);
  }
}

export async function reserveBed(hospitalId, bedType) {
  return caregridRequest(`/api/hospitals/${encodeURIComponent(hospitalId)}/beds/reserve`, {
    method: "POST",
    body: JSON.stringify({ bed_type: bedType }),
  });
}
