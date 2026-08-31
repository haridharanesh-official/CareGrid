from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .. import database, event_bus


LIVE_SECONDS = 15
OFFLINE_SECONDS = 30
MAX_FUTURE_SKEW_SECONDS = 60
NODE_TYPE = "simulated_hospital"
HOSPITAL_ID_PATTERN = re.compile(r"^HOSP-\d{3}$")


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _incoming_timestamp(value: Any) -> datetime:
    parsed = _parse_timestamp(value)
    if parsed > datetime.now(timezone.utc) + timedelta(seconds=MAX_FUTURE_SKEW_SECONDS):
        raise ValueError("timestamp is too far in the future")
    return parsed


def _sequence(payload: dict[str, Any]) -> int:
    value = payload.get("sequence", payload.get("resource_version"))
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("sequence must be a positive integer")
    return value


def _hospital_id(payload: dict[str, Any], topic_hospital_id: str | None = None) -> str:
    hospital_id = str(payload.get("hospital_id") or "").strip().upper()
    if not HOSPITAL_ID_PATTERN.fullmatch(hospital_id):
        raise ValueError("invalid hospital_id")
    if topic_hospital_id and hospital_id != topic_hospital_id:
        raise ValueError("payload hospital_id does not match MQTT topic")
    return hospital_id


def _non_negative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _resource_name(value: Any, field: str) -> str:
    name = str(value).strip()
    if not name or len(name) > 120:
        raise ValueError(f"{field} name must contain 1 to 120 characters")
    return name


def _known_hospital(connection, hospital_id: str) -> None:
    if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
        raise ValueError(f"unknown hospital_id: {hospital_id}")


def _validate_beds(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("resources.beds must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"bed {name} must be an object")
        total = _non_negative_int(item.get("total"), f"beds.{name}.total")
        occupied = _non_negative_int(item.get("occupied"), f"beds.{name}.occupied")
        reserved = _non_negative_int(item.get("reserved", 0), f"beds.{name}.reserved")
        available = _non_negative_int(item.get("available"), f"beds.{name}.available")
        database.validate_bed_state(total, occupied, reserved)
        if available != total - occupied - reserved:
            raise ValueError(f"beds.{name}.available contradicts total/occupied/reserved")
        result[_resource_name(name, "bed").upper()] = {
            "total": total, "occupied": occupied, "reserved": reserved, "available": available,
        }
    return result


def _validate_departments(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("resources.departments must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(item, dict) or not isinstance(item.get("available"), bool):
            raise ValueError(f"department {name} requires boolean available")
        doctors = _non_negative_int(item.get("doctors_on_duty", 0), f"departments.{name}.doctors_on_duty")
        result[_resource_name(name, "department")] = {"available": item["available"], "doctors_on_duty": doctors}
    return result


def _validate_equipment(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("resources.equipment must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"equipment {name} must be an object")
        total = _non_negative_int(item.get("total"), f"equipment.{name}.total")
        available = _non_negative_int(item.get("available"), f"equipment.{name}.available")
        reserved = _non_negative_int(item.get("reserved", 0), f"equipment.{name}.reserved")
        operational = item.get("operational")
        if not isinstance(operational, bool):
            raise ValueError(f"equipment.{name}.operational must be boolean")
        database.validate_equipment_state(total, available, reserved)
        if not operational and available:
            raise ValueError(f"equipment.{name}.available must be zero when equipment is not operational")
        result[_resource_name(name, "equipment")] = {
            "total": total, "available": available, "reserved": reserved, "operational": operational,
        }
    return result


def _validate_pharmacy(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("resources.pharmacy must be a non-empty object")
    result: dict[str, dict[str, Any]] = {}
    for name, item in raw.items():
        if not isinstance(item, dict):
            raise ValueError(f"pharmacy item {name} must be an object")
        total = _non_negative_int(item.get("total_quantity"), f"pharmacy.{name}.total_quantity")
        reserved = _non_negative_int(item.get("reserved_quantity", 0), f"pharmacy.{name}.reserved_quantity")
        available = _non_negative_int(item.get("available_quantity"), f"pharmacy.{name}.available_quantity")
        database.validate_pharmacy_state(total, reserved)
        if available != total - reserved:
            raise ValueError(f"pharmacy.{name}.available_quantity contradicts total/reserved")
        result[_resource_name(name, "pharmacy")] = {
            "total_quantity": total, "reserved_quantity": reserved, "available_quantity": available,
        }
    return result


def validate_resource_payload(
    payload: dict[str, Any], topic_hospital_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("resource payload must be an object")
    hospital_id = _hospital_id(payload, topic_hospital_id)
    if payload.get("node_type") != NODE_TYPE:
        raise ValueError(f"node_type must be {NODE_TYPE}")
    timestamp = _incoming_timestamp(payload.get("timestamp"))
    resources = payload.get("resources")
    if not isinstance(resources, dict):
        raise ValueError("resources must be an object")
    emergency_capability = payload.get("emergency_capability", True)
    icu_capability = payload.get("icu_capability", True)
    if not isinstance(emergency_capability, bool) or not isinstance(icu_capability, bool):
        raise ValueError("capability flags must be boolean")
    return {
        "hospital_id": hospital_id,
        "node_type": NODE_TYPE,
        "sequence": _sequence(payload),
        "timestamp": _iso(timestamp),
        "emergency_capability": emergency_capability,
        "icu_capability": icu_capability,
        "resources": {
            "beds": _validate_beds(resources.get("beds")),
            "departments": _validate_departments(resources.get("departments")),
            "equipment": _validate_equipment(resources.get("equipment")),
            "pharmacy": _validate_pharmacy(resources.get("pharmacy")),
        },
    }


def validate_status_payload(
    payload: dict[str, Any], topic_hospital_id: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("status payload must be an object")
    hospital_id = _hospital_id(payload, topic_hospital_id)
    if not isinstance(payload.get("online"), bool):
        raise ValueError("online must be boolean")
    return {
        "hospital_id": hospital_id,
        "online": payload["online"],
        "timestamp": _iso(_incoming_timestamp(payload.get("timestamp"))),
        "sequence": _sequence(payload),
    }


def _node_freshness_values(item: dict[str, Any], now: datetime) -> tuple[str, float | None]:
    last_seen = item.get("last_seen")
    if not last_seen:
        return "OFFLINE", None
    received = _parse_timestamp(last_seen)
    age = max(0.0, (now - received).total_seconds())
    if not bool(item.get("advertised_online")) or age > OFFLINE_SECONDS:
        return "OFFLINE", age
    if age > LIVE_SECONDS:
        return "STALE", age
    return "LIVE", age


def node_snapshot(item: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    status, age = _node_freshness_values(item, current)
    result = dict(item)
    result["advertised_online"] = bool(result.get("advertised_online"))
    result["online"] = status == "LIVE"
    result["connection_status"] = status
    result["age_seconds"] = round(age, 1) if age is not None else None
    result["resource_source"] = status if status in {"LIVE", "STALE"} else "OFFLINE"
    return result


def _upsert_node(connection, hospital_id: str, node_type: str) -> None:
    now = database.utc_now()
    connection.execute(
        """INSERT OR IGNORE INTO hospital_nodes
           (hospital_id,node_type,advertised_online,last_seen,age_seconds,connection_status,
            resource_version,last_status_sequence,created_at,updated_at)
           VALUES(?,?,0,NULL,NULL,'OFFLINE',0,0,?,?)""",
        (hospital_id, node_type, now, now),
    )
    connection.execute("UPDATE hospital_nodes SET node_type=?,updated_at=? WHERE hospital_id=?", (node_type, now, hospital_id))


def apply_resource_update(
    payload: dict[str, Any], topic_hospital_id: str | None = None,
) -> dict[str, Any]:
    item = validate_resource_payload(payload, topic_hospital_id)
    hospital_id, version, timestamp = item["hospital_id"], item["sequence"], item["timestamp"]
    with database.connect() as connection:
        _known_hospital(connection, hospital_id)
        _upsert_node(connection, hospital_id, item["node_type"])
        current = connection.execute(
            "SELECT resource_version FROM hospital_nodes WHERE hospital_id=?", (hospital_id,)
        ).fetchone()
        if version <= int(current["resource_version"]):
            return {"applied": False, "reason": "stale_sequence", "hospital_id": hospital_id, "resource_version": int(current["resource_version"])}

        resources = item["resources"]
        for bed_type, bed in resources["beds"].items():
            connection.execute(
                """INSERT INTO bed_capacity(hospital_id,bed_type,total,occupied,reserved,status,updated_at)
                   VALUES(?,?,?,?,?,?,?) ON CONFLICT(hospital_id,bed_type) DO UPDATE SET
                   total=excluded.total,occupied=excluded.occupied,reserved=excluded.reserved,
                   status=excluded.status,updated_at=excluded.updated_at""",
                (hospital_id, bed_type, bed["total"], bed["occupied"], bed["reserved"], "available" if bed["available"] else "full", timestamp),
            )
        department_columns = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(departments)")
        }
        for name, department in resources["departments"].items():
            values: dict[str, Any] = {
                "hospital_id": hospital_id,
                "name": name,
                "status": "available" if department["available"] else "offline",
                "doctors_on_duty": department["doctors_on_duty"],
                "created_at": timestamp,
                "updated_at": timestamp,
                "available": int(department["available"]),
            }
            if department_columns["id"]["type"].upper().startswith("TEXT"):
                existing = connection.execute(
                    "SELECT id FROM departments WHERE hospital_id=? AND name=?", (hospital_id, name)
                ).fetchone()
                values["id"] = existing["id"] if existing else f"NODE-DEPT-{hospital_id}-{name.upper().replace(' ', '-')}"
            database.upsert_record(connection, "departments", values, "hospital_id,name")
        for name, equipment in resources["equipment"].items():
            connection.execute(
                """INSERT INTO equipment_inventory(hospital_id,equipment_name,total,available,reserved,operational,updated_at)
                   VALUES(?,?,?,?,?,?,?) ON CONFLICT(hospital_id,equipment_name) DO UPDATE SET
                   total=excluded.total,available=excluded.available,reserved=excluded.reserved,
                   operational=excluded.operational,updated_at=excluded.updated_at""",
                (hospital_id, name, equipment["total"], equipment["available"], equipment["reserved"], int(equipment["operational"]), timestamp),
            )
        pharmacy_columns = {
            row["name"]: row for row in connection.execute("PRAGMA table_info(pharmacy_inventory)")
        }
        for name, medicine in resources["pharmacy"].items():
            status = "out" if medicine["available_quantity"] == 0 else "low" if medicine["available_quantity"] <= 8 else "available"
            existing = connection.execute(
                "SELECT * FROM pharmacy_inventory WHERE hospital_id=? AND medicine_name=?", (hospital_id, name)
            ).fetchone()
            values = {
                "hospital_id": hospital_id,
                "medicine_name": name,
                "total_quantity": medicine["total_quantity"],
                "reserved_quantity": medicine["reserved_quantity"],
                "reorder_level": int(existing["reorder_level"]) if existing else 8,
                "expiry_date": existing["expiry_date"] if existing else timestamp[:10],
                "status": status,
                "updated_at": timestamp,
                "medicine": name,
                "quantity": medicine["total_quantity"],
                "last_updated": timestamp,
            }
            if pharmacy_columns["id"]["type"].upper().startswith("TEXT"):
                values["id"] = existing["id"] if existing else f"NODE-MED-{hospital_id}-{name.upper().replace(' ', '-')}"
            database.upsert_record(connection, "pharmacy_inventory", values, "hospital_id,medicine_name")

        hospital_columns = {row["name"] for row in connection.execute("PRAGMA table_info(hospitals)")}
        updates = ["emergency_enabled=?", "updated_at=?"]
        values: list[Any] = [int(item["emergency_capability"]), timestamp]
        if "icu_available" in hospital_columns:
            updates.append("icu_available=?")
            values.append(int(item["icu_capability"]))
        if "last_updated" in hospital_columns:
            updates.append("last_updated=?")
            values.append(timestamp)
        values.append(hospital_id)
        connection.execute(f"UPDATE hospitals SET {','.join(updates)} WHERE id=?", values)
        connection.execute(
            """UPDATE hospital_nodes SET advertised_online=1,last_seen=?,age_seconds=0,
               connection_status='LIVE',resource_version=?,resource_updated_at=?,updated_at=? WHERE hospital_id=?""",
            (timestamp, version, timestamp, database.utc_now(), hospital_id),
        )

    result = get_node(hospital_id) or {}
    event_bus.publish_event("hospital_node_resources", {"hospital_id": hospital_id, "resource_version": version})
    return {"applied": True, "hospital_id": hospital_id, "resource_version": version, "node": result}


def apply_status_update(
    payload: dict[str, Any], topic_hospital_id: str | None = None,
) -> dict[str, Any]:
    item = validate_status_payload(payload, topic_hospital_id)
    hospital_id, sequence, timestamp = item["hospital_id"], item["sequence"], item["timestamp"]
    with database.connect() as connection:
        _known_hospital(connection, hospital_id)
        _upsert_node(connection, hospital_id, NODE_TYPE)
        row = connection.execute("SELECT * FROM hospital_nodes WHERE hospital_id=?", (hospital_id,)).fetchone()
        if sequence <= int(row["last_status_sequence"]):
            return {"applied": False, "reason": "stale_sequence", "hospital_id": hospital_id, "status_sequence": int(row["last_status_sequence"])}
        previous_seen = _parse_timestamp(row["last_seen"]) if row["last_seen"] else None
        incoming_seen = _parse_timestamp(timestamp)
        last_seen = _iso(max(previous_seen, incoming_seen)) if previous_seen else timestamp
        preview = {"last_seen": last_seen, "advertised_online": item["online"]}
        status, age = _node_freshness_values(preview, datetime.now(timezone.utc))
        connection.execute(
            """UPDATE hospital_nodes SET advertised_online=?,last_seen=?,age_seconds=?,connection_status=?,
               last_status_sequence=?,status_updated_at=?,updated_at=? WHERE hospital_id=?""",
            (int(item["online"]), last_seen, age, status, sequence, timestamp, database.utc_now(), hospital_id),
        )
    result = get_node(hospital_id) or {}
    event_bus.publish_event("hospital_node_status", {"hospital_id": hospital_id, "connection_status": result.get("connection_status")})
    return {"applied": True, "hospital_id": hospital_id, "status_sequence": sequence, "node": result}


def _read_nodes(hospital_id: str | None = None) -> list[dict[str, Any]]:
    with database.connect() as connection:
        if hospital_id:
            rows = connection.execute(
                """SELECT n.*,h.name FROM hospital_nodes n JOIN hospitals h ON h.id=n.hospital_id
                   WHERE n.hospital_id=?""", (hospital_id,),
            ).fetchall()
        else:
            rows = connection.execute(
                """SELECT n.*,h.name FROM hospital_nodes n JOIN hospitals h ON h.id=n.hospital_id
                   ORDER BY n.hospital_id"""
            ).fetchall()
        items = [node_snapshot(dict(row)) for row in rows]
        for item in items:
            connection.execute(
                "UPDATE hospital_nodes SET age_seconds=?,connection_status=? WHERE hospital_id=?",
                (item["age_seconds"], item["connection_status"], item["hospital_id"]),
            )
        return items


def get_node(hospital_id: str) -> dict[str, Any] | None:
    items = _read_nodes(hospital_id)
    return items[0] if items else None


def list_nodes() -> list[dict[str, Any]]:
    return _read_nodes()
