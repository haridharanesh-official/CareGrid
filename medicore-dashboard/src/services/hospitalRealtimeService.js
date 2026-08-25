import { CAREGRID_WS_URL, WARD_DEVICE_ID } from "../config.js";
import { caregridRequest, CareGridApiError } from "./caregridApi.js";

export async function getHospitalLatest() {
  try {
    const latest = await caregridRequest("/api/hospital/latest");
    return { ...latest, _transport: "hospital-rest" };
  } catch (error) {
    if (!(error instanceof CareGridApiError) || error.status !== 404) throw error;
    const [deviceResult, healthResult] = await Promise.allSettled([
      caregridRequest(`/devices/${encodeURIComponent(WARD_DEVICE_ID)}`),
      caregridRequest("/health"),
    ]);
    if (deviceResult.status !== "fulfilled" || !deviceResult.value?.found) {
      throw new CareGridApiError("Hospital ward node is unavailable");
    }
    const device = deviceResult.value.device;
    return {
      nodes: {
        [WARD_DEVICE_ID]: {
          device_id: device.device_id,
          node_type: device.node_type,
          online: device.online,
          last_seen: device.last_seen,
          data: device.data,
        },
      },
      gateway: healthResult.status === "fulfilled" ? healthResult.value : null,
      timestamp: device.last_seen,
      _transport: "legacy-rest",
    };
  }
}

export function createHospitalSocket(handlers, WebSocketImpl = globalThis.WebSocket) {
  if (!CAREGRID_WS_URL || !WebSocketImpl) throw new Error("Hospital realtime URL is not configured");
  const socket = new WebSocketImpl(CAREGRID_WS_URL);
  socket.addEventListener("open", handlers.open);
  socket.addEventListener("message", handlers.message);
  socket.addEventListener("close", handlers.close);
  socket.addEventListener("error", handlers.error);
  return socket;
}

export const getHospitalWebSocketUrl = () => CAREGRID_WS_URL;
