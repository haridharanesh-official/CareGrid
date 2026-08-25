export const CAREGRID_API_URL = (import.meta.env.VITE_CAREGRID_API_URL || "").replace(/\/$/, "");
export const CAREGRID_WS_URL = (import.meta.env.VITE_CAREGRID_WS_URL || CAREGRID_API_URL.replace(/^http/, "ws") + "/ws/hospital").replace(/\/$/, "");
export const DEMO_MODE = String(import.meta.env.VITE_DEMO_MODE ?? "true").toLowerCase() === "true";
export const WARD_DEVICE_ID = "hospital_ward_01";
