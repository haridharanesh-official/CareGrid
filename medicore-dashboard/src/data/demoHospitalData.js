// DEMO / MOCK HOSPITAL DATA: operational fallback only; never used for sensor telemetry.
const HOSPITALS = [
  { id: "HOSP-001", name: "Ganga Hospital", distance: 4.2, eta: 9, score: 96, emergencyBeds: 6, icuBeds: 3, cardiology: true, medicine: true, adrenaline: 18, status: "AVAILABLE" },
  { id: "HOSP-002", name: "PSG Hospitals", distance: 6.8, eta: 13, score: 91, emergencyBeds: 4, icuBeds: 5, cardiology: true, medicine: true, adrenaline: 12, status: "AVAILABLE" },
  { id: "HOSP-003", name: "KMCH", distance: 9.5, eta: 18, score: 88, emergencyBeds: 8, icuBeds: 7, cardiology: true, medicine: true, adrenaline: 25, status: "AVAILABLE" },
  { id: "HOSP-004", name: "Sri Ramakrishna Hospital", distance: 7.4, eta: 15, score: 82, emergencyBeds: 2, icuBeds: 2, cardiology: true, medicine: true, adrenaline: 7, status: "LIMITED" },
  { id: "HOSP-005", name: "Government Medical College Hospital", distance: 11.2, eta: 21, score: 74, emergencyBeds: 3, icuBeds: 1, cardiology: false, medicine: true, adrenaline: 10, status: "LIMITED" },
];

const STOCK = {
  "Ganga Hospital": { Adrenaline: [18, 2], Insulin: [24, 4], Atropine: [10, 1] },
  "PSG Hospitals": { Adrenaline: [12, 1], Insulin: [30, 5], Atropine: [8, 2] },
  KMCH: { Adrenaline: [25, 3], Insulin: [20, 2], Atropine: [15, 1] },
  "Sri Ramakrishna Hospital": { Adrenaline: [7, 1], Insulin: [14, 2], Atropine: [6, 1] },
  "Government Medical College Hospital": { Adrenaline: [10, 2], Insulin: [18, 3], Atropine: [12, 2] },
};

export const getHospitalFallbackData = (criteria = {}) => {
  const department = criteria.department || "Cardiology";
  return HOSPITALS.map((hospital, index) => ({
  ...hospital,
  matchScore: hospital.score,
  connected: true,
  reservable: true,
  demoData: true,
  department,
  departmentAvailable: department === "Cardiology" ? hospital.cardiology : false,
  medicineName: criteria.medicine || "Adrenaline",
  medicineAvailable: hospital.medicine,
  reason: index === 0
    ? "Ganga Hospital is recommended because Cardiology, emergency beds, ICU capacity and Adrenaline are currently available with the shortest suitable ETA."
    : `${hospital.name} matches the requested emergency capacity, clinical capability and medicine requirements with an estimated ${hospital.eta} minute ETA.`,
  })).sort((a, b) => b.score - a.score);
};

export const searchDemoMedicine = (query = "") => {
  const term = query.trim().toLowerCase();
  const updated = new Date().toISOString();
  return Object.entries(STOCK).flatMap(([hospital, medicines], hospitalIndex) =>
    Object.entries(medicines).filter(([medicine]) => medicine.toLowerCase().includes(term)).map(([medicine, [available, reserved]], medicineIndex) => ({
      id: `DEMO-STOCK-${hospitalIndex + 1}-${medicineIndex + 1}`,
      hospital,
      medicine,
      available,
      reserved,
      reorder_level: 5,
      updated,
      demoData: true,
    })),
  );
};
