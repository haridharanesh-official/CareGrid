import { caregridRequest } from "./caregridApi.js";

export const getGatewayHealth = () => caregridRequest("/health");
export const getDevices = () => caregridRequest("/devices");
export const getDevice = id => caregridRequest(`/devices/${encodeURIComponent(id)}`);
export const getRecentEvents = (limit = 25) => caregridRequest(`/events/recent?limit=${limit}`);
