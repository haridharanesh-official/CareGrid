import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

const read=path=>readFile(new URL(path,import.meta.url),"utf8");
test("hospital realtime service uses the requested REST and WebSocket contracts",async()=>{const service=await read("../src/services/hospitalRealtimeService.js"),config=await read("../src/config.js");assert.ok(service.includes("/api/hospital/latest"));assert.ok(config.includes("/ws/hospital"));assert.match(service,/new WebSocketImpl/)});
test("deployed legacy REST support still uses real Pi data",async()=>{const source=await read("../src/services/hospitalRealtimeService.js");assert.ok(source.includes("/devices/"));assert.ok(source.includes("legacy-rest"));assert.equal(source.includes("demoWardPayload"),false)});
test("provider never imports or substitutes demo sensor telemetry",async()=>{const source=await read("../src/app/providers.jsx");assert.equal(source.includes("demoSensor"),false);assert.equal(source.includes("demoWardPayload"),false);assert.ok(source.includes("useCareGridRealtime"))});
test("client source contains no MQTT credentials or direct MQTT client",async()=>{const files=["../src/services/hospitalRealtimeService.js","../src/hooks/useCareGridRealtime.js","../src/app/providers.jsx"];for(const file of files){const source=(await read(file)).toLowerCase();assert.equal(source.includes("mqtt_password"),false);assert.equal(source.includes("mqtt://"),false);assert.equal(source.includes("mosquitto"),false)}});
test("sensor UI does not hardcode readings or the Pi address",async()=>{const files=["../src/pages/nurse/RealtimeDashboard.jsx","../src/pages/nurse/RealtimeRFID.jsx","../src/hooks/useCareGridRealtime.js"];for(const file of files){const source=await read(file);assert.equal(source.includes("10.15.43.187"),false);assert.equal(source.includes("Math.random"),false)}});
test("demo role switcher remains explicitly gated",async()=>{const source=await read("../src/layouts/RoleLayout.jsx");assert.match(source,/DEMO_MODE&&/)});
