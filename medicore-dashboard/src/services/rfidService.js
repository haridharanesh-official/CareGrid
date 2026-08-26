import { caregridRequest } from "./caregridApi.js";
import { getDemoRfidResult, normalizeUid } from "../data/demoPatientData.js";

export async function resolveRfidUid(uid) {
  if (!uid) return null;
  const normalized = normalizeUid(uid);
  try {
    const response = await caregridRequest(`/api/rfid/${encodeURIComponent(normalized)}`, { timeoutMs:1800 });
    return { ...response, found:response.found ?? response.known ?? false, type:response.type || response.entity_type, record:response.record || response.entity, offline_fallback:false };
  } catch {
    return getDemoRfidResult(normalized);
  }
}
