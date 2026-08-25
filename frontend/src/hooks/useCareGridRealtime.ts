import { useCallback, useEffect, useRef, useState } from "react";
import type {
  CareGridNode,
  HospitalLatestResponse,
  HospitalWebSocketMessage,
} from "../lib/caregrid";

export type GatewayConnectionState =
  | "LIVE"
  | "RECONNECTING"
  | "OFFLINE";

const API_BASE =
  process.env.NEXT_PUBLIC_CAREGRID_API_URL ??
  "http://10.15.43.187:8000";

const WS_BASE =
  process.env.NEXT_PUBLIC_CAREGRID_WS_URL ??
  "ws://10.15.43.187:8000";

const MAX_RECONNECT_DELAY_MS = 15000;

export function useCareGridRealtime() {
  const [nodes, setNodes] = useState<Record<string, CareGridNode>>({});
  const [gatewayStatus, setGatewayStatus] =
    useState<GatewayConnectionState>("RECONNECTING");
  const [lastMessageAt, setLastMessageAt] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptRef = useRef(0);
  const stoppedRef = useRef(false);

  const loadInitialState = useCallback(async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);

    try {
      const response = await fetch(`${API_BASE}/api/hospital/latest`, {
        cache: "no-store",
        signal: controller.signal,
      });

      if (!response.ok) {
        throw new Error(`CareGrid API returned ${response.status}`);
      }

      const payload = (await response.json()) as HospitalLatestResponse;
      setNodes(payload.nodes ?? {});
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to reach CareGrid API",
      );
    } finally {
      clearTimeout(timeout);
    }
  }, []);

  useEffect(() => {
    stoppedRef.current = false;
    void loadInitialState();

    const connect = () => {
      if (stoppedRef.current) return;

      if (
        wsRef.current &&
        (wsRef.current.readyState === WebSocket.OPEN ||
          wsRef.current.readyState === WebSocket.CONNECTING)
      ) {
        return;
      }

      setGatewayStatus("RECONNECTING");

      const socket = new WebSocket(`${WS_BASE}/ws/hospital`);
      wsRef.current = socket;

      socket.onopen = () => {
        if (stoppedRef.current) {
          socket.close();
          return;
        }

        reconnectAttemptRef.current = 0;
        setGatewayStatus("LIVE");
        setError(null);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as HospitalWebSocketMessage;

          if (payload.type === "hospital_update" && payload.nodes) {
            setNodes(payload.nodes);
            setLastMessageAt(new Date());
            setGatewayStatus("LIVE");
            setError(null);
          }
        } catch {
          setError("Received invalid realtime data from CareGrid");
        }
      };

      socket.onerror = () => {
        setError("CareGrid realtime connection encountered an error");
      };

      socket.onclose = () => {
        wsRef.current = null;
        if (stoppedRef.current) return;

        setGatewayStatus("RECONNECTING");
        reconnectAttemptRef.current += 1;

        const delay = Math.min(
          1000 * Math.pow(2, reconnectAttemptRef.current - 1),
          MAX_RECONNECT_DELAY_MS,
        );

        reconnectTimerRef.current = setTimeout(connect, delay);
      };
    };

    connect();

    return () => {
      stoppedRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [loadInitialState]);

  useEffect(() => {
    const timer = setInterval(() => {
      if (!lastMessageAt) return;
      const ageMs = Date.now() - lastMessageAt.getTime();
      if (ageMs > 20000 && gatewayStatus === "LIVE") {
        setGatewayStatus("RECONNECTING");
      }
    }, 5000);

    return () => clearInterval(timer);
  }, [gatewayStatus, lastMessageAt]);

  return {
    nodes,
    gatewayStatus,
    lastMessageAt,
    error,
    refresh: loadInitialState,
  };
}
