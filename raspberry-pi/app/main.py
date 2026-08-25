from __future__ import annotations

import asyncio
import copy
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

MQTT_HOST = os.getenv("CAREGRID_MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("CAREGRID_MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("CAREGRID_MQTT_USERNAME", "caregrid")
MQTT_PASSWORD = os.getenv("CAREGRID_MQTT_PASSWORD", "")
DB_PATH = Path(
    os.getenv(
        "CAREGRID_DB_PATH",
        str(BASE_DIR / "data" / "caregrid.db"),
    )
)

app = FastAPI(
    title="CareGrid Raspberry Pi Gateway",
    version="0.3.1",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


mqtt_connected = False
mqtt_lock = threading.Lock()
state_lock = threading.Lock()
device_state: dict[str, dict[str, Any]] = {}

# ESP32 telemetry is currently published about every 5 seconds.
DEVICE_STALE_SECONDS = 15
DEVICE_OFFLINE_SECONDS = 30


class TelemetryEnvelope(BaseModel):
    device_id: str
    node_type: str
    timestamp: str | None = None
    data: dict[str, Any]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso_time(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except (TypeError, ValueError):
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def device_connection_status(
    state: dict[str, Any],
) -> tuple[str, bool, float | None]:
    """
    Derive physical node availability from telemetry freshness.

    LIVE    <= 15 seconds since telemetry
    STALE   >15 and <=30 seconds
    OFFLINE >30 seconds
    """

    last_seen = parse_iso_time(
        state.get("last_seen")
    )

    if last_seen is None:
        return "OFFLINE", False, None

    age = max(
        0.0,
        (
            datetime.now(timezone.utc)
            - last_seen
        ).total_seconds(),
    )

    if age <= DEVICE_STALE_SECONDS:
        return "LIVE", True, age

    if age <= DEVICE_OFFLINE_SECONDS:
        return "STALE", False, age

    return "OFFLINE", False, age


def snapshot() -> dict[str, dict[str, Any]]:
    with state_lock:
        states = copy.deepcopy(device_state)

    for state in states.values():
        (
            connection_status,
            online,
            age_seconds,
        ) = device_connection_status(state)

        state["online"] = online
        state["connection_status"] = (
            connection_status
        )
        state["age_seconds"] = (
            round(age_seconds, 1)
            if age_seconds is not None
            else None
        )

    return states


def topic_device_id(topic: str) -> str | None:
    parts = topic.split("/")

    if (
        len(parts) >= 5
        and parts[0] == "caregrid"
        and parts[1] == "hospital"
        and parts[2] == "ward"
    ):
        return (
            f"hospital_{parts[3].replace('-', '_')}"
        )

    if (
        len(parts) >= 4
        and parts[0] == "caregrid"
        and parts[1] == "ambulance"
    ):
        return parts[2]

    return None


def init_db() -> None:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

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

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS emergency_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                topic TEXT NOT NULL,
                device_id TEXT NOT NULL,
                panic INTEGER NOT NULL,
                status TEXT NOT NULL
            )
            """
        )

        conn.commit()


def store_telemetry(
    topic: str,
    event: TelemetryEnvelope,
) -> None:
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
                event.model_dump_json(),
            ),
        )

        conn.commit()


def store_emergency(
    topic: str,
    device_id: str,
    panic: bool,
) -> None:
    status = (
        "PANIC"
        if panic
        else "NORMAL"
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO emergency_events
                (received_at, topic, device_id, panic, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                utc_now(),
                topic,
                device_id,
                1 if panic else 0,
                status,
            ),
        )

        conn.commit()


def normalize_telemetry(
    payload: Any,
) -> TelemetryEnvelope:
    if not isinstance(payload, dict):
        raise ValueError(
            "telemetry payload must be a JSON object"
        )

    if "data" in payload:
        return TelemetryEnvelope.model_validate(
            payload
        )

    if (
        "device_id" not in payload
        or "node_type" not in payload
    ):
        return TelemetryEnvelope.model_validate(
            payload
        )

    metadata = {
        "device_id",
        "node_type",
        "timestamp",
    }

    return TelemetryEnvelope.model_validate(
        {
            "device_id": payload["device_id"],
            "node_type": payload["node_type"],
            "timestamp": payload.get("timestamp"),
            "data": {
                key: value
                for key, value in payload.items()
                if key not in metadata
            },
        }
    )


HA_ENTITIES: list[
    tuple[
        str,
        str,
        str,
        str,
        dict[str, Any],
    ]
] = [
    ("heart_rate", "Heart Rate", "sensor", "{{ value_json.data.vitals.heart_rate }}", {"unit_of_measurement": "bpm", "device_class": "heart_rate", "state_class": "measurement"}),
    ("spo2", "SpO2", "sensor", "{{ value_json.data.vitals.spo2 }}", {"unit_of_measurement": "%", "state_class": "measurement"}),
    ("vitals_valid", "Vitals Valid", "binary_sensor", "{{ 'ON' if value_json.data.vitals.valid else 'OFF' }}", {}),
    ("lux", "Light Level", "sensor", "{{ value_json.data.environment.lux }}", {"unit_of_measurement": "lx", "device_class": "illuminance", "state_class": "measurement"}),
    ("temperature", "Temperature", "sensor", "{{ value_json.data.environment.temperature_c }}", {"unit_of_measurement": "°C", "device_class": "temperature", "state_class": "measurement"}),
    ("pressure", "Atmospheric Pressure", "sensor", "{{ value_json.data.environment.pressure_hpa }}", {"unit_of_measurement": "hPa", "device_class": "atmospheric_pressure", "state_class": "measurement"}),
    ("pm1", "PM1", "sensor", "{{ value_json.data.environment.pm1 }}", {"unit_of_measurement": "µg/m³", "state_class": "measurement"}),
    ("pm25", "PM2.5", "sensor", "{{ value_json.data.environment.pm25 }}", {"unit_of_measurement": "µg/m³", "device_class": "pm25", "state_class": "measurement"}),
    ("pm10", "PM10", "sensor", "{{ value_json.data.environment.pm10 }}", {"unit_of_measurement": "µg/m³", "device_class": "pm10", "state_class": "measurement"}),
    ("bin_distance", "Medical Waste Bin Distance", "sensor", "{{ value_json.data.bin.distance_cm }}", {"unit_of_measurement": "cm", "device_class": "distance", "state_class": "measurement"}),
    ("bin_fill", "Medical Waste Bin Fill", "sensor", "{{ value_json.data.bin.fill_percent }}", {"unit_of_measurement": "%", "state_class": "measurement"}),
    ("bin_full", "Medical Waste Bin Full", "binary_sensor", "{{ 'ON' if value_json.data.bin.full else 'OFF' }}", {"device_class": "problem"}),
    ("bed_vibration", "Bed Vibration", "binary_sensor", "{{ 'ON' if value_json.data.bed.vibration else 'OFF' }}", {"device_class": "vibration"}),
    ("panic", "Patient Panic Button", "binary_sensor", "{{ 'ON' if value_json.data.emergency.panic else 'OFF' }}", {"device_class": "safety"}),
    ("mq_adc", "MQ Sensor ADC", "sensor", "{{ value_json.data.air.adc }}", {"state_class": "measurement"}),
    ("mq_voltage", "MQ Sensor Voltage", "sensor", "{{ value_json.data.air.sensor_voltage }}", {"unit_of_measurement": "V", "device_class": "voltage", "state_class": "measurement"}),
    ("mq_anomaly", "Air Vapor Anomaly", "binary_sensor", "{{ 'ON' if value_json.data.air.anomaly else 'OFF' }}", {"device_class": "problem"}),
    ("last_rfid", "Last RFID Identification", "sensor", "{{ value_json.data.rfid.last_uid }}", {}),
    ("wifi_rssi", "ESP32 WiFi Signal", "sensor", "{{ value_json.data.health.wifi_rssi }}", {"unit_of_measurement": "dBm", "device_class": "signal_strength", "state_class": "measurement"}),
    ("mqtt_connected", "ESP32 MQTT Connected", "binary_sensor", "{{ 'ON' if value_json.data.health.mqtt else 'OFF' }}", {"device_class": "connectivity"}),
    ("pms5003_health", "PMS5003 Health", "binary_sensor", "{{ 'ON' if value_json.data.health.pms5003 else 'OFF' }}", {"device_class": "connectivity"}),
    ("max30100_health", "MAX30100 Health", "binary_sensor", "{{ 'ON' if value_json.data.health.max30100 else 'OFF' }}", {"device_class": "connectivity"}),
    ("rc522_health", "RC522 Health", "binary_sensor", "{{ 'ON' if value_json.data.health.rc522 else 'OFF' }}", {"device_class": "connectivity"}),
]


def publish_home_assistant_discovery(
    client: mqtt.Client,
    event: TelemetryEnvelope,
) -> None:
    state_topic = (
        f"caregrid/state/{event.device_id}"
    )

    availability_topic = (
        f"caregrid/device/"
        f"{event.device_id}/availability"
    )

    device = {
        "identifiers": [
            f"caregrid_{event.device_id}"
        ],
        "name": (
            "CareGrid Smart Hospital Ward 01"
        ),
        "manufacturer": "CareGrid",
        "model": event.node_type,
    }

    for (
        suffix,
        name,
        component,
        template,
        extra,
    ) in HA_ENTITIES:
        object_id = (
            f"caregrid_{event.device_id}_{suffix}"
            .replace("-", "_")
        )

        config: dict[str, Any] = {
            "name": name,
            "unique_id": object_id,
            "state_topic": state_topic,
            "availability_topic": availability_topic,
            "value_template": template,
            "device": device,
        }

        if component == "binary_sensor":
            config.update(
                {
                    "payload_on": "ON",
                    "payload_off": "OFF",
                }
            )

        config.update(extra)

        client.publish(
            f"homeassistant/{component}/"
            f"{object_id}/config",
            json.dumps(config),
            qos=1,
            retain=True,
        )

    client.publish(
        availability_topic,
        "online",
        qos=1,
        retain=True,
    )

    client.publish(
        state_topic,
        event.model_dump_json(),
        qos=1,
        retain=True,
    )


def update_telemetry_state(
    client: mqtt.Client,
    event: TelemetryEnvelope,
) -> None:
    with state_lock:
        previous = device_state.get(
            event.device_id,
            {},
        )

        device_state[event.device_id] = {
            "device_id": event.device_id,
            "node_type": event.node_type,
            "last_seen": utc_now(),
            "online": True,
            "mqtt_status": previous.get(
                "mqtt_status",
                "online",
            ),
            "mqtt_status_updated_at": (
                previous.get(
                    "mqtt_status_updated_at"
                )
            ),
            "data": event.data,
        }

    publish_home_assistant_discovery(
        client,
        event,
    )


def update_panic_state(
    device_id: str,
    panic: bool,
) -> None:
    """
    Panic state is merged without refreshing last_seen.

    Reason: /panic is retained. A retained NORMAL message received
    after a gateway restart must not make a disconnected ward LIVE.
    """

    with state_lock:
        state = device_state.setdefault(
            device_id,
            {
                "device_id": device_id,
                "node_type": (
                    "smart_hospital_ward"
                ),
                "last_seen": None,
                "online": False,
                "data": {},
            },
        )

        state.setdefault(
            "data",
            {},
        )["emergency"] = {
            "panic": panic,
            "status": (
                "PANIC"
                if panic
                else "NORMAL"
            ),
            "updated_at": utc_now(),
        }


def update_online_state(
    device_id: str,
    online: bool,
) -> None:
    """
    Record ESP32 MQTT/LWT state separately.

    A retained 'online' message is not proof of current physical
    connectivity, so it does not refresh last_seen.
    """

    with state_lock:
        state = device_state.setdefault(
            device_id,
            {
                "device_id": device_id,
                "node_type": (
                    "smart_hospital_ward"
                ),
                "last_seen": None,
                "online": False,
                "data": {},
            },
        )

        state["mqtt_status"] = (
            "online"
            if online
            else "offline"
        )

        state["mqtt_status_updated_at"] = (
            utc_now()
        )

        if not online:
            state["online"] = False


def on_connect(
    client: mqtt.Client,
    userdata: Any,
    flags: Any,
    reason_code: mqtt.ReasonCode,
    properties: Any = None,
) -> None:
    global mqtt_connected

    if reason_code.is_failure:
        with mqtt_lock:
            mqtt_connected = False

        print(
            f"[MQTT] Connection failed: "
            f"{reason_code}"
        )
        return

    with mqtt_lock:
        mqtt_connected = True

    for topic in (
        "caregrid/hospital/+/+/telemetry",
        "caregrid/hospital/+/+/panic",
        "caregrid/hospital/+/+/status",
        "caregrid/ambulance/+/telemetry",
    ):
        client.subscribe(
            topic,
            qos=1,
        )

    client.publish(
        "caregrid/system/raspberry-pi/status",
        json.dumps(
            {
                "status": "online",
                "timestamp": utc_now(),
            }
        ),
        qos=1,
        retain=True,
    )

    print(
        "[MQTT] Connected to broker "
        f"{MQTT_HOST}:{MQTT_PORT}"
    )


def on_disconnect(
    client: mqtt.Client,
    userdata: Any,
    disconnect_flags: Any,
    reason_code: mqtt.ReasonCode,
    properties: Any = None,
) -> None:
    global mqtt_connected

    with mqtt_lock:
        mqtt_connected = False

    if reason_code.is_failure:
        print(
            "[MQTT] Disconnected unexpectedly: "
            f"{reason_code}"
        )


def on_message(
    client: mqtt.Client,
    userdata: Any,
    message: mqtt.MQTTMessage,
) -> None:
    topic = message.topic

    try:
        raw = message.payload.decode(
            "utf-8"
        )
    except UnicodeDecodeError as exc:
        print(
            f"[MQTT] Invalid UTF-8 "
            f"on {topic}: {exc}"
        )
        return

    if topic.endswith("/panic"):
        device_id = (
            topic_device_id(topic)
            or "hospital_ward_01"
        )

        value = raw.strip().upper()

        if value not in {
            "EMERGENCY",
            "NORMAL",
        }:
            print(
                "[PANIC] Ignoring unknown payload "
                f"on {topic}: {raw!r}"
            )
            return

        panic = (
            value == "EMERGENCY"
        )

        update_panic_state(
            device_id,
            panic,
        )

        store_emergency(
            topic,
            device_id,
            panic,
        )

        if panic:
            client.publish(
                "caregrid/alerts/emergency",
                json.dumps(
                    {
                        "type": "patient_panic",
                        "device_id": device_id,
                        "status": "PANIC",
                        "timestamp": utc_now(),
                    }
                ),
                qos=1,
            )

            print(
                "[PANIC] EMERGENCY ACTIVE: "
                f"{device_id}"
            )
        else:
            print(
                f"[PANIC] CLEARED: "
                f"{device_id}"
            )

        return

    if topic.endswith("/status"):
        device_id = topic_device_id(
            topic
        )

        value = raw.strip().lower()

        if (
            device_id
            and value in {
                "online",
                "offline",
            }
        ):
            update_online_state(
                device_id,
                value == "online",
            )

            print(
                f"[STATUS] {device_id}: "
                f"{value}"
            )

        return

    if topic.endswith("/telemetry"):
        try:
            event = normalize_telemetry(
                json.loads(raw)
            )

            store_telemetry(
                topic,
                event,
            )

            update_telemetry_state(
                client,
                event,
            )

        except (
            json.JSONDecodeError,
            ValidationError,
            ValueError,
        ) as exc:
            print(
                "[MQTT] Invalid telemetry "
                f"on {topic}: {exc}"
            )

            client.publish(
                "caregrid/alerts/gateway",
                json.dumps(
                    {
                        "type": (
                            "invalid_telemetry"
                        ),
                        "topic": topic,
                        "error": str(exc),
                        "timestamp": utc_now(),
                    }
                ),
                qos=1,
            )


mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="caregrid-pi-gateway",
)

mqtt_client.username_pw_set(
    MQTT_USERNAME,
    MQTT_PASSWORD,
)

mqtt_client.will_set(
    "caregrid/system/raspberry-pi/status",
    json.dumps(
        {
            "status": "offline",
            "timestamp": utc_now(),
        }
    ),
    qos=1,
    retain=True,
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_message = on_message


@app.on_event("startup")
def startup() -> None:
    init_db()

    mqtt_client.connect_async(
        MQTT_HOST,
        MQTT_PORT,
        keepalive=60,
    )

    mqtt_client.loop_start()

    print(
        "[CAREGRID] Raspberry Pi gateway starting"
    )


@app.on_event("shutdown")
def shutdown() -> None:
    try:
        mqtt_client.publish(
            "caregrid/system/raspberry-pi/status",
            json.dumps(
                {
                    "status": "offline",
                    "timestamp": utc_now(),
                }
            ),
            qos=1,
            retain=True,
        )

        mqtt_client.disconnect()

    finally:
        mqtt_client.loop_stop()


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "service": (
            "CareGrid Raspberry Pi Gateway"
        ),
        "status": "running",
        "version": "0.3.1",
        "realtime_api": (
            "/api/hospital/latest"
        ),
        "websocket": "/ws/hospital",
        "freshness": {
            "live_seconds": (
                DEVICE_STALE_SECONDS
            ),
            "offline_seconds": (
                DEVICE_OFFLINE_SECONDS
            ),
        },
    }


@app.get("/health")
def health() -> dict[str, Any]:
    with mqtt_lock:
        connected = mqtt_connected

    with state_lock:
        registered = len(
            device_state
        )

    return {
        "status": (
            "healthy"
            if connected
            else "degraded"
        ),
        "mqtt_connected": connected,
        "registered_devices": registered,
        "database": str(DB_PATH),
        "timestamp": utc_now(),
    }


@app.get("/devices")
def devices() -> dict[str, Any]:
    states = list(
        snapshot().values()
    )

    return {
        "count": len(states),
        "devices": states,
    }


@app.get("/devices/{device_id}")
def device(
    device_id: str,
) -> dict[str, Any]:
    item = snapshot().get(
        device_id
    )

    if item is None:
        return {
            "found": False,
            "device_id": device_id,
        }

    return {
        "found": True,
        "device": item,
    }


def hospital_nodes() -> dict[str, dict[str, Any]]:
    return {
        key: value
        for key, value
        in snapshot().items()
        if (
            str(
                value.get(
                    "node_type",
                    "",
                )
            ).startswith(
                "smart_hospital"
            )
            or key.startswith(
                "hospital_"
            )
        )
    }


@app.get("/api/hospital/latest")
def hospital_latest() -> dict[str, Any]:
    return {
        "status": "ok",
        "timestamp": utc_now(),
        "nodes": hospital_nodes(),
    }


@app.get(
    "/api/hospital/{device_id}"
)
def hospital_device(
    device_id: str,
) -> dict[str, Any]:
    item = snapshot().get(
        device_id
    )

    if item is None:
        return {
            "found": False,
            "device_id": device_id,
        }

    return {
        "found": True,
        "device": item,
        "timestamp": utc_now(),
    }


@app.websocket("/ws/hospital")
async def hospital_websocket(
    websocket: WebSocket,
) -> None:
    await websocket.accept()

    print(
        "[WS] Hospital frontend connected"
    )

    try:
        while True:
            await websocket.send_json(
                {
                    "type": "hospital_update",
                    "timestamp": utc_now(),
                    "nodes": hospital_nodes(),
                }
            )

            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print(
            "[WS] Hospital frontend disconnected"
        )

    except Exception as exc:
        print(
            f"[WS] Connection error: {exc}"
        )


@app.get("/events/recent")
def recent_events(
    limit: int = 20,
) -> dict[str, Any]:
    safe = max(
        1,
        min(limit, 100),
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                id,
                received_at,
                topic,
                device_id,
                node_type,
                payload_json
            FROM telemetry_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe,),
        ).fetchall()

    events = []

    for row in rows:
        item = dict(row)

        item["payload"] = json.loads(
            item.pop("payload_json")
        )

        events.append(item)

    return {
        "count": len(events),
        "events": events,
    }


@app.get("/api/emergencies/recent")
def recent_emergencies(
    limit: int = 20,
) -> dict[str, Any]:
    safe = max(
        1,
        min(limit, 100),
    )

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                id,
                received_at,
                topic,
                device_id,
                panic,
                status
            FROM emergency_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (safe,),
        ).fetchall()

    events = []

    for row in rows:
        item = dict(row)

        item["panic"] = bool(
            item["panic"]
        )

        events.append(item)

    return {
        "count": len(events),
        "events": events,
    }
