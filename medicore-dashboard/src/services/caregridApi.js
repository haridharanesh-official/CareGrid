import { CAREGRID_API_URL } from "../config.js";

export class CareGridApiError extends Error {
  constructor(message, status = 0) { super(message); this.name = "CareGridApiError"; this.status = status; }
}

export function shouldUseDemoFallback(error) {
  return error instanceof CareGridApiError && (error.status === 0 || error.status === 404 || error.status >= 500);
}

export async function caregridRequest(path, options = {}) {
  if (!CAREGRID_API_URL) throw new CareGridApiError("CareGrid API URL is not configured");
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs || 4500);
  try {
    const response = await fetch(`${CAREGRID_API_URL}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      signal: controller.signal,
    });
    if (!response.ok) throw new CareGridApiError(`CareGrid API returned ${response.status}`, response.status);
    return await response.json();
  } catch (error) {
    if (error.name === "AbortError") throw new CareGridApiError("CareGrid Gateway request timed out");
    if (error instanceof CareGridApiError) throw error;
    throw new CareGridApiError("CareGrid Gateway Offline");
  } finally { clearTimeout(timeout); }
}
