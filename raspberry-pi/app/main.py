from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, ValidationError

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

MQTT_HOST = os.getenv("CAREGRID_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("CAREGRID_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("CAREGRID_MQTT_USERNAME", "caregrid")
MQTT_PASSWORD = os.getenv("CAREGRID_MQTT_PASSWORD", "")
DB_PATH = Path(os.getenv("CAREGRID_DB_PATH", str(BASE_DIR / "data" / "caregrid.db")))

app = FastAPI(title="CareGrid Raspberry Pi Gateway", version="0.2.1")

mqtt_connected = False
mqtt_lock = threading.Lock()
state_lock = threading.Lock()
device_state: dict[str, dict[str, Any]] = {}


class TelemetryEnvelope(BaseModel):
    device_id: str
    node_type: str
    timestamp: str | None = None
    data: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                device_id TEXT NOT NULL,
                node_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            )
            """
        )
        conn.commit()


def store_event(topic: str, event: TelemetryEnvelope) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO telemetry_events
                (received_at, topic, device_id, node_type, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                topic,
                event.device_id,
                event.node_type,
                json.dumps(event.model_dump(), separators=(",", ":")),
            ),
        )
        conn.commit()


def normalize_telemetry(payload: Any) -> tuple[TelemetryEnvelope, bool]:
    """Normalize supported CareGrid telemetry formats.

    Returns (event, gateway_discovery_allowed).

    Supported formats:
    1. Canonical CareGrid envelope:
       {"device_id": "...", "node_type": "...", "data": {...}}
    2. Native ESP32-S3 hospital ward payload where sensor groups such as
       bed/ward/vitals/environment are top-level keys.

    The ESP32 hospital ward firmware already publishes its own Home Assistant
    discovery configuration, so gateway discovery is disabled for format 2 to
    avoid duplicate entities.
    """
    if not isinstance(payload, dict):
        raise ValueError("telemetry payload must be a JSON object")

    if "data" in payload:
        return TelemetryEnvelope.model_validate(payload), True

    if "device_id" not in payload or "node_type" not in payload:
        return TelemetryEnvelope.model_validate(payload), False

    metadata_keys = {"device_id", "node_type", "timestamp"}
    native_data = {key: value for key, value in payload.items() if key not in metadata_keys}

    normalized = {
        "device_id": payload["device_id"],
        "node_type": payload["node_type"],
        "timestamp": payload.get("timestamp"),
        "data": native_data,
    }
    return TelemetryEnvelope.model_validate(normalized), False


def discovery_component(value: Any) -> str:
    return "binary_sensor" if isinstance(value, bool) else "sensor"


def publish_home_assistant_discovery(client: mqtt.Client, event: TelemetryEnvelope) -> None:
    state_topic = f"caregrid/state/{event.device_id}"
    availability_topic = f"caregrid/device/{event.device_id}/availability"

    # Generic gateway discovery is intentionally limited to scalar values.
    # Complex/nested devices such as the ESP32 hospital ward publish their own
    # discovery config with precise templates and units.
    for key, value in event.data.items():
        if isinstance(value, (dict, list)) or value is None:
            continue

        component = discovery_component(value)
        object_id = f"caregrid_{event.device_id}_{key}".replace("-", "_")
        config_topic = f"homeassistant/{component}/{object_id}/config"

        config: dict[str, Any] = {
            "name": f"{event.device_id} {key.replace('_', ' ').title()}",
            "unique_id": object_id,
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "device": {
                "identifiers": [f"caregrid_{event.device_id}"],
                "name": event.device_id,
                "manufacturer": "CareGrid",
                "model": event.node_type,
            },
        }

        if component == "binary_sensor":
            config["value_template"] = f"{{{{ 'ON' if value_json.data.{key} else 'OFF' }}}}"
            config["payload_on"] = "ON"
            config["payload_off"] = "OFF"
        else:
            config["value_template"] = f"{{{{ value_json.data.{key} }}}}"

        client.publish(config_topic, json.dumps(config), qos=1, retain=True)

    client.publish(availability_topic, "online", qos=1, retain=True)
    client.publish(state_topic, event.model_dump_json(), qos=1, retain=True)


def update_live_state(
    client: mqtt.Client,
    event: TelemetryEnvelope,
    *,
    publish_discovery: bool,
) -> None:
    state = {
        "device_id": event.device_id,
        "node_type": event.node_type,
        "last_seen": utc_now(),
        "online": True,
        "data": event.data,
    }
    with state_lock:
        device_state[event.device_id] = state

    if publish_discovery:
        publish_home_assistant_discovery(client, event)


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: mqtt.ReasonCode, properties: Any = None) -> None:
    global mqtt_connected

    if not reason_code.is_failure:
        with mqtt_lock:
            mqtt_connected = True

        client.subscribe("caregrid/hospital/+/+/telemetry", qos=1)
        client.subscribe("caregrid/ambulance/+/telemetry", qos=1)
        client.publish(
            "caregrid/system/raspberry-pi/status",
            json.dumps({"status": "online", "timestamp": utc_now()}),
            qos=1,
            retain=True,
        )
    else:
        with mqtt_lock:
            mqtt_connected = False
        print(f"MQTT connection failed: {reason_code}")


def on_disconnect(client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: mqtt.ReasonCode, properties: Any = None) -> None:
    global mqtt_connected
    with mqtt_lock:
        mqtt_connected = False

    if reason_code.is_failure:
        print(f"MQTT disconnected unexpectedly: {reason_code}")


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    try:
        raw = message.payload.decode("utf-8")
        parsed = json.loads(raw)
        event, gateway_discovery_allowed = normalize_telemetry(parsed)
        store_event(message.topic, event)
        update_live_state(
            client,
            event,
            publish_discovery=gateway_discovery_allowed,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        client.publish(
            "caregrid/alerts/gateway",
            json.dumps(
                {
                    "type": "invalid_telemetry",
                    "topic": message.topic,
                    "error": str(exc),
                    "timestamp": utc_now(),
                }
            ),
            qos=1,
        )


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="caregrid-pi-gateway")
mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
mqtt_client.will_set(
    "caregrid/system/raspberry-pi/status",
    json.dumps({"status": "offline"}),
    qos=1,
    retain=True,
)
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


@app.on_event("startup")
def startup() -> None:
    init_db()
    mqtt_client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()


@app.on_event("shutdown")
def shutdown() -> None:
    try:
        mqtt_client.publish(
            "caregrid/system/raspberry-pi/status",
            json.dumps({"status": "offline", "timestamp": utc_now()}),
            qos=1,
            retain=True,
        )
        mqtt_client.disconnect()
    finally:
        mqtt_client.loop_stop()


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": "CareGrid Raspberry Pi Gateway",
        "status": "running",
        "version": "0.2.1",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    with mqtt_lock:
        connected = mqtt_connected
    with state_lock:
        registered_devices = len(device_state)

    return {
        "status": "healthy" if connected else "degraded",
        "mqtt_connected": connected,
        "registered_devices": registered_devices,
        "database": str(DB_PATH),
        "timestamp": utc_now(),
    }


@app.get("/devices")
def devices() -> dict[str, Any]:
    with state_lock:
        devices_snapshot = list(device_state.values())
    return {"count": len(devices_snapshot), "devices": devices_snapshot}


@app.get("/devices/{device_id}")
def device(device_id: str) -> dict[str, Any]:
    with state_lock:
        item = device_state.get(device_id)
    if item is None:
        return {"found": False, "device_id": device_id}
    return {"found": True, "device": item}


@app.get("/events/recent")
def recent_events(limit: int = 20) -> dict[str, Any]:
    safe_limit = max(1, min(limit, 100))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, received_at, topic, device_id, node_type, payload_json
            FROM telemetry_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe_limit,),
        ).fetchall()

    events = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json"))
        events.append(item)

    return {"count": len(events), "events": events}
