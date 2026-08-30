from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .. import database, event_bus
from . import hospital_recommendation_service


CASE_STATUSES = {
    "CREATED", "HOSPITAL_RECOMMENDED", "DESTINATION_CONFIRMED", "PREALERT_SENT",
    "ACKNOWLEDGED", "EN_ROUTE", "ARRIVED", "CLOSED", "CANCELLED",
}
PREALERT_STATUSES = {"PENDING", "SENT", "ACKNOWLEDGED", "CANCELLED"}


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _json(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _event(connection, case_id: str, event_type: str, message: str, *, actor_type: str = "system", actor_id: str | None = None, metadata: dict[str, Any] | None = None) -> None:
    connection.execute(
        """INSERT INTO emergency_case_events
           (id,case_id,event_type,message,actor_type,actor_id,metadata_json,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (f"EVT-{uuid.uuid4().hex[:12].upper()}", case_id, event_type, message, actor_type, actor_id,
         json.dumps(metadata or {}, separators=(",", ":")), database.utc_now()),
    )


def _next_case_number(connection) -> str:
    year = datetime.now(timezone.utc).year
    key = f"emergency_case_{year}"
    connection.execute("INSERT OR IGNORE INTO caregrid_sequences(name,value) VALUES(?,0)", (key,))
    connection.execute("UPDATE caregrid_sequences SET value=value+1 WHERE name=?", (key,))
    value = int(connection.execute("SELECT value FROM caregrid_sequences WHERE name=?", (key,)).fetchone()[0])
    return f"CG-EMR-{year}-{value:06d}"


def _case_payload(connection, row) -> dict[str, Any]:
    item = dict(row)
    item["simulation"] = bool(item.get("simulation", 1))
    item["recommendation_snapshot"] = _json(item.pop("recommendation_snapshot_json", None), None)
    item["equipment_required"] = _json(item.get("equipment_required"), [])
    patient = None
    if item.get("patient_id"):
        patient_row = connection.execute("SELECT * FROM patients WHERE patient_id=?", (item["patient_id"],)).fetchone()
        patient = dict(patient_row) if patient_row else None
    item["patient_context"] = patient
    item["incident_type"] = item.get("category")
    item["requested_department"] = item.get("department_required")
    item["requested_bed"] = item.get("bed_type_required")
    item["hospital_id"] = item.get("selected_hospital_id")
    item["destination"] = item.get("selected_hospital_name")
    item["patient"] = item.get("patient_name") or (patient or {}).get("name")
    item["last_updated"] = item.get("updated_at")
    item["demo_data"] = item["simulation"]
    return item


def _prealert_payload(row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = _json(item.pop("payload_json", None), {})
    item["delivery_status"] = item["status"]
    item["deliveryStatus"] = "Delivered" if item["status"] in {"SENT", "ACKNOWLEDGED"} else item["status"]
    item["emergency_case_id"] = item["case_id"]
    item["demo_data"] = True
    return item


def _load_case(connection, case_id: str):
    return connection.execute("SELECT * FROM emergency_cases WHERE id=?", (case_id,)).fetchone()


def create_case(payload: dict[str, Any]) -> dict[str, Any]:
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else {}
    patient = payload.get("patient") if isinstance(payload.get("patient"), dict) else {}
    vitals = payload.get("vitals") if isinstance(payload.get("vitals"), dict) else {}
    requirements = payload.get("requirements") if isinstance(payload.get("requirements"), dict) else {}
    location = payload.get("location") if isinstance(payload.get("location"), dict) else {}
    rfid_uid = str(_first(patient, "rfid_uid", "rfid") or _first(payload, "rfid_uid", "rfid") or "").strip().upper() or None
    patient_id = _first(patient, "patient_id", "id") or _first(payload, "patient_id", "patientId")
    patient_name = _first(patient, "name") or _first(payload, "patient_name", "name")
    now = database.utc_now()
    case_id = f"EMR-{uuid.uuid4().hex[:12].upper()}"

    with database.connect() as connection:
        if rfid_uid:
            assignment = connection.execute(
                "SELECT entity_id FROM rfid_assignments WHERE uid=? AND entity_type='patient' AND active=1", (rfid_uid,)
            ).fetchone()
            if assignment:
                patient_id = assignment["entity_id"]
        if patient_id:
            patient_row = connection.execute("SELECT name FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
            if patient_row is None:
                raise ValueError("Patient not found")
            patient_name = patient_row["name"]
        case_number = _next_case_number(connection)
        equipment = _first(requirements, "equipment", "equipment_required") or _first(payload, "equipment", "equipment_required") or []
        if isinstance(equipment, str):
            equipment = [value.strip() for value in equipment.split(",") if value.strip()]
        connection.execute(
            """INSERT INTO emergency_cases
               (id,case_number,status,severity,category,incident_type,ambulance_id,patient_id,patient_name,patient_age,patient_gender,
                rfid_uid,heart_rate,spo2,department_required,bed_type_required,medicine_required,equipment_required,
                requested_department,requested_bed,ambulance_latitude,ambulance_longitude,created_at,last_updated,updated_at,source,simulation)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (case_id, case_number, "CREATED", str(_first(incident, "severity") or _first(payload, "severity") or "HIGH").upper(),
             str(_first(incident, "category", "type") or _first(payload, "category", "incident_type") or "Emergency"),
             str(_first(incident, "category", "type") or _first(payload, "category", "incident_type") or "Emergency"),
             _first(payload, "ambulance_id", "ambulanceId") or "AMB-108", patient_id, patient_name,
             _first(patient, "age") if "age" in patient else _first(payload, "patient_age", "age"),
             _first(patient, "gender") or _first(payload, "patient_gender", "gender"), rfid_uid,
             _first(vitals, "heart_rate", "heartRate") if vitals else _first(payload, "heart_rate", "heartRate"),
             _first(vitals, "spo2") if vitals else _first(payload, "spo2"),
             _first(requirements, "department", "department_required") or _first(payload, "department_required", "department"),
             _first(requirements, "bed_type", "bed_type_required") or _first(payload, "bed_type_required", "bedType", "requested_bed"),
             _first(requirements, "medicine", "medicine_required") or _first(payload, "medicine_required", "medicine"), json.dumps(equipment),
             _first(requirements, "department", "department_required") or _first(payload, "department_required", "department"),
             _first(requirements, "bed_type", "bed_type_required") or _first(payload, "bed_type_required", "bedType", "requested_bed"),
             _first(location, "latitude") if location else _first(payload, "ambulance_latitude", "latitude"),
             _first(location, "longitude") if location else _first(payload, "ambulance_longitude", "longitude"),
             now, now, now, str(payload.get("source") or "ambulance_operator")),
        )
        _event(connection, case_id, "CASE_CREATED", f"Emergency case {case_number} created", actor_type="ambulance")
        row = _load_case(connection, case_id)
    event_bus.publish_event("emergency_case_created", {"case_id": case_id, "case_number": case_number})
    with database.connect() as connection:
        return _case_payload(connection, row)


def list_cases(*, status: str | None = None, hospital_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if status:
        normalized = status.strip().upper()
        if normalized not in CASE_STATUSES:
            raise ValueError("Unsupported case status")
        clauses.append("status=?")
        values.append(normalized)
    if hospital_id:
        clauses.append("selected_hospital_id=?")
        values.append(hospital_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(max(1, min(int(limit), 100)))
    with database.connect() as connection:
        rows = connection.execute(f"SELECT * FROM emergency_cases{where} ORDER BY created_at DESC LIMIT ?", values).fetchall()
        return [_case_payload(connection, row) for row in rows]


def get_case(case_id: str) -> dict[str, Any] | None:
    with database.connect() as connection:
        row = _load_case(connection, case_id)
        if row is None:
            return None
        case = _case_payload(connection, row)
        prealert_row = connection.execute("SELECT * FROM hospital_prealerts WHERE case_id=?", (case_id,)).fetchone()
        events = connection.execute("SELECT * FROM emergency_case_events WHERE case_id=? ORDER BY rowid", (case_id,)).fetchall()
        case["prealert"] = _prealert_payload(prealert_row) if prealert_row else None
        case["events"] = [{**dict(event), "metadata": _json(event["metadata_json"], {})} for event in events]
        return case


def recommend_case(case_id: str) -> dict[str, Any] | None:
    with database.connect() as connection:
        row = _load_case(connection, case_id)
        if row is None:
            return None
        case = dict(row)
        if case["status"] not in {"CREATED", "HOSPITAL_RECOMMENDED"}:
            raise ValueError(f"Case cannot be recommended from status {case['status']}")
    result = hospital_recommendation_service.recommend_hospitals(
        department=case.get("department_required"), requested_bed=case.get("bed_type_required"),
        medicine=case.get("medicine_required"), icu_required=str(case.get("bed_type_required") or "").upper() == "ICU",
        emergency_required=True, latitude=case.get("ambulance_latitude"), longitude=case.get("ambulance_longitude"),
    )
    generated_at = database.utc_now()
    snapshot = {**result, "generated_at": generated_at}
    with database.connect() as connection:
        connection.execute(
            "UPDATE emergency_cases SET status='HOSPITAL_RECOMMENDED',recommendation_snapshot_json=?,updated_at=? WHERE id=?",
            (json.dumps(snapshot, separators=(",", ":")), generated_at, case_id),
        )
        _event(connection, case_id, "RECOMMENDATION_GENERATED", f"{result['count']} eligible hospitals ranked", metadata={"recommended_hospital_id": (result.get("recommended") or {}).get("hospital", {}).get("id")})
        updated = _load_case(connection, case_id)
    event_bus.publish_event("recommendation_generated", {"case_id": case_id, "case_number": case["case_number"], "eligible_count": result["count"]})
    with database.connect() as connection:
        return {**result, "case": _case_payload(connection, updated)}


def _build_prealert_payload(connection, case: dict[str, Any], recommendation: dict[str, Any], hospital: dict[str, Any], created_at: str) -> dict[str, Any]:
    patient = None
    if case.get("patient_id"):
        row = connection.execute("SELECT patient_id,name,blood_group FROM patients WHERE patient_id=?", (case["patient_id"],)).fetchone()
        patient = dict(row) if row else None
    return {
        "case_number": case["case_number"],
        "patient": {
            "patient_id": case.get("patient_id"), "name": case.get("patient_name"),
            "rfid_uid": case.get("rfid_uid"), "blood_group": (patient or {}).get("blood_group"),
        },
        "incident": {"category": case.get("category"), "severity": case.get("severity")},
        "vitals": {"heart_rate": case.get("heart_rate"), "spo2": case.get("spo2")},
        "requirements": {
            "department": case.get("department_required"), "bed_type": case.get("bed_type_required"),
            "medicine": case.get("medicine_required"), "equipment": _json(case.get("equipment_required"), []),
        },
        "destination": {
            "hospital_id": hospital["id"], "hospital_name": hospital["name"],
            "recommendation_score": recommendation["score"], "eta_minutes": recommendation["eta_minutes"],
        },
        "created_at": created_at,
        "simulation": True,
    }


def confirm_destination(case_id: str, hospital_id: str) -> dict[str, Any] | None:
    now = database.utc_now()
    published: dict[str, Any] | None = None
    with database.connect() as connection:
        row = _load_case(connection, case_id)
        if row is None:
            return None
        case = dict(row)
        existing = connection.execute("SELECT * FROM hospital_prealerts WHERE case_id=?", (case_id,)).fetchone()
        if case["status"] in {"PREALERT_SENT", "ACKNOWLEDGED", "ARRIVED", "CLOSED"}:
            if case.get("selected_hospital_id") != hospital_id:
                raise ValueError("Destination is already confirmed for another hospital")
            return {"case": _case_payload(connection, row), "prealert": _prealert_payload(existing) if existing else None, "idempotent": True}
        if case["status"] != "HOSPITAL_RECOMMENDED":
            raise ValueError(f"Destination cannot be confirmed from status {case['status']}")
        snapshot = _json(case.get("recommendation_snapshot_json"), {})
        recommendation = next((item for item in snapshot.get("items", []) if item.get("hospital", {}).get("id") == hospital_id and item.get("eligibility") == "eligible"), None)
        if recommendation is None:
            raise ValueError("Selected hospital was not eligible in the stored recommendation")
        hospital = recommendation["hospital"]
        connection.execute(
            """UPDATE emergency_cases SET status='DESTINATION_CONFIRMED',selected_hospital_id=?,selected_hospital_name=?,
               hospital_id=?,recommendation_score=?,eta_minutes=?,confirmed_at=?,last_updated=?,updated_at=? WHERE id=?""",
            (hospital_id, hospital["name"], hospital_id, recommendation["score"], recommendation["eta_minutes"], now, now, now, case_id),
        )
        _event(connection, case_id, "DESTINATION_CONFIRMED", f"Operator confirmed {hospital['name']}", actor_type="ambulance_operator", metadata={"hospital_id": hospital_id, "score": recommendation["score"]})
        prealert_id = f"PRE-{uuid.uuid4().hex[:12].upper()}"
        payload = _build_prealert_payload(connection, case, recommendation, hospital, now)
        connection.execute(
            """INSERT INTO hospital_prealerts
               (id,case_id,emergency_case_id,hospital_id,status,priority,payload_json,created_at,sent_at,updated_at)
               VALUES(?,?,?,?,'SENT',?,?,?,?,?)""",
            (prealert_id, case_id, case_id, hospital_id, case.get("severity"), json.dumps(payload, separators=(",", ":")), now, now, now),
        )
        connection.execute("UPDATE emergency_cases SET status='PREALERT_SENT',updated_at=? WHERE id=?", (now, case_id))
        _event(connection, case_id, "PREALERT_SENT", f"CareGrid pre-alert created for {hospital['name']}", metadata={"prealert_id": prealert_id, "hospital_id": hospital_id})
        updated = _load_case(connection, case_id)
        prealert = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
        published = {"case_id": case_id, "case_number": case["case_number"], "prealert_id": prealert_id, "hospital_id": hospital_id}
        result = {"case": _case_payload(connection, updated), "prealert": _prealert_payload(prealert), "idempotent": False}
    event_bus.publish_event("destination_confirmed", published)
    event_bus.publish_event("prealert_created", published)
    return result


def list_prealerts(*, hospital_id: str | None = None, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if hospital_id:
        clauses.append("hospital_id=?")
        values.append(hospital_id)
    if status:
        normalized = status.strip().upper()
        if normalized not in PREALERT_STATUSES:
            raise ValueError("Unsupported pre-alert status")
        clauses.append("status=?")
        values.append(normalized)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(max(1, min(int(limit), 100)))
    with database.connect() as connection:
        rows = connection.execute(f"SELECT * FROM hospital_prealerts{where} ORDER BY created_at DESC LIMIT ?", values).fetchall()
        return [_prealert_payload(row) for row in rows]


def get_prealert(prealert_id: str) -> dict[str, Any] | None:
    with database.connect() as connection:
        row = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
        return _prealert_payload(row) if row else None


def acknowledge_prealert(prealert_id: str, acknowledged_by: str | None = None) -> dict[str, Any] | None:
    now = database.utc_now()
    with database.connect() as connection:
        row = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
        if row is None:
            return None
        if row["status"] == "ACKNOWLEDGED":
            return {"prealert": _prealert_payload(row), "case": _case_payload(connection, _load_case(connection, row["case_id"])), "idempotent": True}
        if row["status"] != "SENT":
            raise ValueError(f"Pre-alert cannot be acknowledged from status {row['status']}")
        actor = (acknowledged_by or "NURSE-DEMO-001").strip()
        connection.execute("UPDATE hospital_prealerts SET status='ACKNOWLEDGED',acknowledged_at=?,acknowledged_by=?,updated_at=? WHERE id=?", (now, actor, now, prealert_id))
        connection.execute("UPDATE emergency_cases SET status='ACKNOWLEDGED',updated_at=? WHERE id=?", (now, row["case_id"]))
        _event(connection, row["case_id"], "PREALERT_ACKNOWLEDGED", f"Pre-alert acknowledged by {actor}", actor_type="nurse", actor_id=actor, metadata={"prealert_id": prealert_id})
        updated_alert = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
        updated_case = _load_case(connection, row["case_id"])
        case_number = updated_case["case_number"]
        result = {"prealert": _prealert_payload(updated_alert), "case": _case_payload(connection, updated_case), "idempotent": False}
    event_bus.publish_event("prealert_acknowledged", {"case_id": row["case_id"], "case_number": case_number, "prealert_id": prealert_id})
    return result


def _transition(case_id: str, *, expected: set[str], target: str, timestamp_column: str, event_type: str, websocket_type: str) -> dict[str, Any] | None:
    now = database.utc_now()
    with database.connect() as connection:
        row = _load_case(connection, case_id)
        if row is None:
            return None
        if row["status"] == target:
            return _case_payload(connection, row)
        if row["status"] not in expected:
            raise ValueError(f"Case cannot transition from {row['status']} to {target}")
        connection.execute(f"UPDATE emergency_cases SET status=?,{timestamp_column}=?,updated_at=? WHERE id=?", (target, now, now, case_id))
        _event(connection, case_id, event_type, f"Case status changed to {target}")
        updated = _load_case(connection, case_id)
        case_number = updated["case_number"]
        result = _case_payload(connection, updated)
    event_bus.publish_event(websocket_type, {"case_id": case_id, "case_number": case_number})
    return result


def mark_arrived(case_id: str) -> dict[str, Any] | None:
    return _transition(case_id, expected={"PREALERT_SENT", "ACKNOWLEDGED", "EN_ROUTE"}, target="ARRIVED", timestamp_column="arrived_at", event_type="ARRIVED", websocket_type="emergency_arrived")


def close_case(case_id: str) -> dict[str, Any] | None:
    return _transition(case_id, expected={"ARRIVED"}, target="CLOSED", timestamp_column="closed_at", event_type="CLOSED", websocket_type="emergency_closed")


def update_case(case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    if "status" in payload:
        status = str(payload["status"]).strip().upper().replace(" ", "_")
        if status == "ARRIVED":
            return mark_arrived(case_id)
        if status == "CLOSED":
            return close_case(case_id)
        raise ValueError("Use the lifecycle endpoints for status transitions")
    field_map = {"heart_rate": "heart_rate", "heartRate": "heart_rate", "spo2": "spo2", "eta": "eta_minutes", "eta_minutes": "eta_minutes"}
    changes = {field_map[key]: value for key, value in payload.items() if key in field_map}
    if not changes:
        raise ValueError("No supported case fields supplied")
    changes["updated_at"] = database.utc_now()
    with database.connect() as connection:
        row = _load_case(connection, case_id)
        if row is None:
            return None
        assignments = ",".join(f"{key}=?" for key in changes)
        connection.execute(f"UPDATE emergency_cases SET {assignments} WHERE id=?", (*changes.values(), case_id))
        return _case_payload(connection, _load_case(connection, case_id))
