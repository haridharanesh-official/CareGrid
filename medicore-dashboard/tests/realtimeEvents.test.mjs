import test from "node:test";
import assert from "node:assert/strict";
import { deriveRealtimeEvents, reconnectDelay } from "../src/services/realtimeEventService.js";

const state = (overrides = {}) => ({
  updatedAt: "2026-08-25T11:00:00.000Z",
  emergency: { panic: false },
  bed: { vibration: false },
  rfid: { lastUid: null },
  connectivity: { mqtt: true },
  ...overrides,
});

test("panic press and release create immediate log events", () => {
  const pressed = state({ emergency: { panic: true } });
  assert.equal(deriveRealtimeEvents(state(), pressed)[0].message, "PATIENT PANIC ALERT — WARD 01");
  assert.equal(deriveRealtimeEvents(pressed, state())[0].type, "panic-resolved");
});

test("RFID scans and vibration edges are recorded without inventing identities", () => {
  const next = state({ bed: { vibration: true }, rfid: { lastUid: "D0:DA:F6:5F" } });
  const events = deriveRealtimeEvents(state(), next);
  assert.deepEqual(events.map(({ type }) => type), ["vibration", "rfid"]);
  assert.match(events[1].message, /D0:DA:F6:5F/);
});

test("reconnect delay uses capped exponential backoff", () => {
  assert.deepEqual([1, 2, 3, 4, 10].map(reconnectDelay), [1000, 2000, 4000, 8000, 30000]);
});
