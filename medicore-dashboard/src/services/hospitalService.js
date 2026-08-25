import { caregridRequest } from "./caregridApi.js";

const normalizeRecommendation = item => {
  const hospital = item.hospital || item;
  const distance = Number(item.distance ?? 0);
  const medicineQuantity = item.availability?.medicine_quantity;
  return {
    ...hospital,
    id: hospital.id,
    name: hospital.name,
    score: Number(item.score ?? 0),
    distance,
    eta: Math.max(3, Math.round(distance * 3 + 4)),
    emergencyBeds: hospital.emergency_beds_available ?? 0,
    icuBeds: hospital.icu_beds_available ?? 0,
    normalBeds: hospital.normal_beds_available ?? 0,
    connected: hospital.status === "online",
    medicine: medicineQuantity == null ? true : medicineQuantity > 0,
    reservable: item.eligibility ? item.eligibility === "eligible" : hospital.status === "online",
    reason: item.reason || "Operational CareGrid demo hospital.",
    availability: item.availability || {},
    demoData: Boolean(hospital.demo_data),
  };
};

export async function getHospitals() {
  const response = await caregridRequest("/api/hospitals/recommend");
  return (response.items || []).map(normalizeRecommendation);
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
  const response = await caregridRequest(`/api/hospitals/recommend?${params}`);
  return (response.items || []).map(normalizeRecommendation);
}

export async function reserveBed(hospitalId, bedType) {
  return caregridRequest(`/api/hospitals/${encodeURIComponent(hospitalId)}/beds/reserve`, {
    method: "POST",
    body: JSON.stringify({ bed_type: bedType }),
  });
}
