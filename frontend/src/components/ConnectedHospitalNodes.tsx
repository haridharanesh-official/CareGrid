import type { CareGridNode } from "../lib/caregrid";
import { useCareGridRealtime } from "../hooks/useCareGridRealtime";

function formatLastSeen(value: string | null) {
  if (!value) return "Never";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unknown";

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function statusClasses(status: CareGridNode["connection_status"]) {
  if (status === "LIVE") {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  if (status === "STALE") {
    return "bg-amber-50 text-amber-700 border-amber-200";
  }
  return "bg-red-50 text-red-700 border-red-200";
}

function WardCard({
  node,
  onOpen,
}: {
  node: CareGridNode;
  onOpen?: (node: CareGridNode) => void;
}) {
  const isLive = node.connection_status === "LIVE";
  const wifiRssi = node.data?.health?.wifi_rssi;
  const mqttConnected = node.data?.health?.mqtt === true;

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-xl font-semibold text-slate-950">
          Ward 01 · {node.device_id}
        </h2>

        <span
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusClasses(
            node.connection_status,
          )}`}
        >
          {node.connection_status}
        </span>
      </div>

      <dl className="mt-6 divide-y divide-slate-100">
        <div className="flex items-center justify-between py-3">
          <dt className="text-slate-500">Node type</dt>
          <dd className="rounded-full bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            {node.node_type}
          </dd>
        </div>

        <div className="flex items-center justify-between py-3">
          <dt className="text-slate-500">Wi-Fi</dt>
          <dd
            className={
              typeof wifiRssi === "number"
                ? "font-medium text-emerald-700"
                : "font-medium text-slate-500"
            }
          >
            {typeof wifiRssi === "number" ? `${wifiRssi} dBm` : "Unavailable"}
          </dd>
        </div>

        <div className="flex items-center justify-between py-3">
          <dt className="text-slate-500">MQTT</dt>
          <dd
            className={
              mqttConnected
                ? "font-medium text-emerald-700"
                : "font-medium text-red-700"
            }
          >
            {mqttConnected ? "Connected" : "Disconnected"}
          </dd>
        </div>

        <div className="flex items-center justify-between py-3">
          <dt className="text-slate-500">Last telemetry</dt>
          <dd className="font-medium text-slate-800">
            {formatLastSeen(node.last_seen)}
          </dd>
        </div>

        <div className="flex items-center justify-between py-3">
          <dt className="text-slate-500">Telemetry age</dt>
          <dd className="font-medium text-slate-800">
            {typeof node.age_seconds === "number"
              ? `${node.age_seconds.toFixed(1)} s`
              : "Unknown"}
          </dd>
        </div>
      </dl>

      <div className="mt-5">
        <button
          type="button"
          disabled={!isLive}
          onClick={() => {
            if (isLive) onOpen?.(node);
          }}
          className={[
            "rounded-xl border px-4 py-2 text-sm font-semibold transition",
            isLive
              ? "border-slate-300 bg-white text-slate-950 hover:bg-slate-50"
              : "cursor-not-allowed border-slate-200 bg-slate-100 text-slate-400",
          ].join(" ")}
        >
          {isLive
            ? "Open live ward"
            : node.connection_status === "STALE"
              ? "Ward signal stale"
              : "Ward offline"}
        </button>
      </div>
    </article>
  );
}

export default function ConnectedHospitalNodes() {
  const { nodes, gatewayStatus, error } = useCareGridRealtime();
  const hospitalNodes = Object.values(nodes);

  return (
    <main className="min-h-screen bg-slate-50 px-8 py-10">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8 flex items-start justify-between gap-6">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-950">
              Connected hospital nodes
            </h1>
            <p className="mt-2 text-lg text-slate-500">
              Node status is derived from actual telemetry freshness.
            </p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
            <div className="flex items-center gap-2">
              <span
                className={[
                  "h-2.5 w-2.5 rounded-full",
                  gatewayStatus === "LIVE"
                    ? "bg-emerald-500"
                    : gatewayStatus === "RECONNECTING"
                      ? "bg-amber-500"
                      : "bg-red-500",
                ].join(" ")}
              />
              <span className="text-sm font-semibold text-slate-900">
                Gateway {gatewayStatus}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Raspberry Pi API / WebSocket
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-6 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {error}
          </div>
        )}

        {hospitalNodes.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <p className="font-medium text-slate-900">No hospital nodes reported</p>
            <p className="mt-2 text-sm text-slate-500">
              Start the ESP32 ward node and check MQTT connectivity.
            </p>
          </div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {hospitalNodes.map((node) => (
              <WardCard
                key={node.device_id}
                node={node}
                onOpen={() => {
                  window.location.href = `/nurse/live-ward?device=${encodeURIComponent(
                    node.device_id,
                  )}`;
                }}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
