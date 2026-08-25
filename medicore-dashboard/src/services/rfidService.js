import { caregridRequest } from "./caregridApi.js";

export async function resolveRfidUid(uid) {
  if (!uid) return null;
  return caregridRequest(`/api/rfid/${encodeURIComponent(uid)}`);
}
