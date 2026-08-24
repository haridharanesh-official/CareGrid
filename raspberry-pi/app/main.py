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

app = FastAPI(title="CareGrid Raspberry Pi Gateway", version="0.1.0")

mqtt_connected = False
mqtt_lock = threading.Lock()


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


def on_connect(client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any = None) -> None:
    global mqtt_connected
    if int(reason_code) == 0:
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


def on_disconnect(client: mqtt.Client, userdata: Any, disconnect_flags: Any, reason_code: Any, properties: Any = None) -> None:
    global mqtt_connected
    with mqtt_lock:
        mqtt_connected = False


def on_message(client: mqtt.Client, userdata: Any, message: mqtt.MQTTMessage) -> None:
    try:
        raw = message.payload.decode("utf-8")
        parsed = json.loads(raw)
        event = TelemetryEnvelope.model_validate(parsed)
        store_event(message.topic, event)
    except (UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
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
        "version": "0.1.0",
    }


@app.get("/health")
def health() -> dict[str, Any]:
    with mqtt_lock:
        connected = mqtt_connected
    return {
        "status": "healthy" if connected else "degraded",
        "mqtt_connected": connected,
        "database": str(DB_PATH),
        "timestamp": utc_now(),
    }


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
