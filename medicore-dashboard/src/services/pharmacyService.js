import { caregridRequest } from "./caregridApi.js";

const normalize = item => {
  const available = Math.max(0, item.available ?? item.available_quantity ?? item.quantity - item.reserved_quantity);
  return {
    ...item,
    id: item.id,
    hospital: item.hospital,
    quantity: available,
    reserved: item.reserved ?? item.reserved_quantity,
    updated: new Date(item.updated ?? item.last_updated).toLocaleDateString(),
    travel: "—",
    status: available <= 0 ? "out" : available <= item.reorder_level ? "low" : "available",
  };
};

export async function getPharmacyInventory() {
  const response = await caregridRequest("/api/pharmacy/search?query=");
  return (response.results || []).map(normalize);
}

export async function searchMedicine(query) {
  const response = await caregridRequest(`/api/pharmacy/search?query=${encodeURIComponent(query || "")}`);
  return (response.results || []).map(normalize);
}

export async function getCrossHospitalMedicineAvailability(query) {
  return searchMedicine(query);
}

export async function reserveMedicine() {
  throw new Error("Medicine reservation requires backend transaction support");
}

export async function dispenseMedicine() {
  throw new Error("Medicine dispensing requires backend transaction support");
}
