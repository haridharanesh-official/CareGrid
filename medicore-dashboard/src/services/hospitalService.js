import { caregridRequest } from "./caregridApi.js";

// DEMO / MOCK HOSPITAL DATA: used only when the recommendation API is unavailable.
const DEMO_HOSPITALS = [
  { id: "demo-ganga", name: "Ganga Hospital", distance: 4.2, eta: 9, score: 96, emergencyBeds: 6, icuBeds: 3, cardiology: true, adrenaline: 18, ventilators: 4, status: "AVAILABLE" },
  { id: "demo-psg", name: "PSG Hospitals", distance: 6.8, eta: 13, score: 91, emergencyBeds: 4, icuBeds: 5, cardiology: true, adrenaline: 12, ventilators: 6, status: "AVAILABLE" },
  { id: "demo-kmch", name: "KMCH", distance: 9.5, eta: 18, score: 88, emergencyBeds: 8, icuBeds: 7, cardiology: true, adrenaline: 25, ventilators: 9, status: "AVAILABLE" },
  { id: "demo-ramakrishna", name: "Sri Ramakrishna Hospital", distance: 7.4, eta: 15, score: 82, emergencyBeds: 2, icuBeds: 2, cardiology: true, adrenaline: 7, ventilators: 3, status: "LIMITED" },
  { id: "demo-government-medical-college", name: "Government Medical College Hospital", distance: 11.2, eta: 21, score: 74, emergencyBeds: 3, icuBeds: 1, cardiology: false, adrenaline: 10, ventilators: 2, status: "LIMITED" },
];

const demoRecommendations = criteria => DEMO_HOSPITALS.map((hospital, index) => ({
  ...hospital,
  matchScore: hospital.score,
  connected: true,
  reservable: true,
  demoData: true,
  department: criteria.department || "Cardiology",
  departmentAvailable: criteria.department === "Cardiology" ? hospital.cardiology : false,
  medicineName: criteria.medicine || "Adrenaline",
  medicineAvailable: hospital.adrenaline > 0,
  reason: index === 0
    ? "Ganga Hospital is recommended because Cardiology, emergency beds, ICU capacity and Adrenaline are currently available with the shortest suitable ETA."
    : `${hospital.name} matches the requested emergency capacity, clinical capability and medicine requirements with an estimated ${hospital.eta} minute ETA.`,
})).sort((a, b) => b.score - a.score);

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
  try {
    const response = await caregridRequest(`/api/hospitals/recommend?${params}`);
    return (response.items || response.recommendations || []).map(normalizeRecommendation).sort((a, b) => b.score - a.score);
  } catch {
    return demoRecommendations(criteria);
  }
}

export async function reserveBed(hospitalId, bedType) {
  return caregridRequest(`/api/hospitals/${encodeURIComponent(hospitalId)}/beds/reserve`, {
    method: "POST",
    body: JSON.stringify({ bed_type: bedType }),
  });
}
