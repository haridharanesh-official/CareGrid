from __future__ import annotations

import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Query

from . import database as resource_database
from .repositories import hospital_repository

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")
DB_PATH = Path(os.getenv("CAREGRID_DB_PATH", str(BASE_DIR / "data" / "caregrid.db")))

hospital_router = APIRouter(prefix="/api", tags=["Hospital demo data"])


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect_db() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS hospitals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    address TEXT NOT NULL,
    phone TEXT NOT NULL,
    emergency_enabled INTEGER NOT NULL CHECK (emergency_enabled IN (0, 1)),
    icu_available INTEGER NOT NULL CHECK (icu_available IN (0, 1)),
    emergency_beds_total INTEGER NOT NULL CHECK (emergency_beds_total >= 0),
    emergency_beds_available INTEGER NOT NULL CHECK (emergency_beds_available BETWEEN 0 AND emergency_beds_total),
    icu_beds_total INTEGER NOT NULL CHECK (icu_beds_total >= 0),
    icu_beds_available INTEGER NOT NULL CHECK (icu_beds_available BETWEEN 0 AND icu_beds_total),
    normal_beds_total INTEGER NOT NULL CHECK (normal_beds_total >= 0),
    normal_beds_available INTEGER NOT NULL CHECK (normal_beds_available BETWEEN 0 AND normal_beds_total),
    operating_rooms_available INTEGER NOT NULL CHECK (operating_rooms_available >= 0),
    blood_bank_available INTEGER NOT NULL CHECK (blood_bank_available IN (0, 1)),
    oxygen_available INTEGER NOT NULL CHECK (oxygen_available IN (0, 1)),
    ventilators_available INTEGER NOT NULL CHECK (ventilators_available >= 0),
    status TEXT NOT NULL,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    available INTEGER NOT NULL DEFAULT 1 CHECK (available IN (0, 1)),
    UNIQUE (hospital_id, name)
);

CREATE TABLE IF NOT EXISTS beds (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    ward TEXT NOT NULL,
    bed_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('available', 'reserved', 'occupied', 'cleaning', 'unavailable')),
    patient_id TEXT REFERENCES patients(patient_id),
    reserved_for TEXT,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pharmacy_inventory (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    medicine TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity >= 0),
    reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
    reorder_level INTEGER NOT NULL CHECK (reorder_level >= 0),
    expiry_date TEXT NOT NULL,
    last_updated TEXT NOT NULL,
    UNIQUE (hospital_id, medicine),
    CHECK (reserved_quantity <= quantity)
);

CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    blood_group TEXT,
    allergies TEXT NOT NULL DEFAULT 'none recorded',
    condition TEXT,
    emergency_contact TEXT,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS nurses (
    nurse_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rfid_assignments (
    uid TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('patient', 'doctor', 'nurse', 'reserved')),
    entity_id TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    assigned_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS emergency_cases (
    id TEXT PRIMARY KEY,
    ambulance_id TEXT,
    patient_id TEXT REFERENCES patients(patient_id),
    hospital_id TEXT REFERENCES hospitals(id),
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    heart_rate REAL,
    spo2 REAL,
    requested_department TEXT,
    requested_bed TEXT,
    eta_minutes INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hospital_prealerts (
    id TEXT PRIMARY KEY,
    emergency_case_id TEXT NOT NULL REFERENCES emergency_cases(id) ON DELETE CASCADE,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS medicine_reservations (
    id TEXT PRIMARY KEY,
    inventory_id TEXT NOT NULL REFERENCES pharmacy_inventory(id),
    emergency_case_id TEXT REFERENCES emergency_cases(id),
    patient_id TEXT REFERENCES patients(patient_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_events (
    id TEXT PRIMARY KEY,
    patient_id TEXT REFERENCES patients(patient_id),
    hospital_id TEXT REFERENCES hospitals(id),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_departments_hospital ON departments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_beds_hospital ON beds(hospital_id, bed_type, status);
CREATE INDEX IF NOT EXISTS idx_pharmacy_medicine ON pharmacy_inventory(medicine);
CREATE INDEX IF NOT EXISTS idx_patient_events_patient ON patient_events(patient_id, created_at DESC);
"""

# Patient, RFID and emergency workflow tables remain owned by this module. The
# multi-hospital capacity/inventory tables are owned by database.py.
DOMAIN_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    blood_group TEXT,
    allergies TEXT NOT NULL DEFAULT 'none recorded',
    condition TEXT,
    emergency_contact TEXT,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS doctors (
    doctor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS nurses (
    nurse_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    demo INTEGER NOT NULL DEFAULT 1 CHECK (demo IN (0, 1)),
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS beds (
    id TEXT PRIMARY KEY,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id) ON DELETE CASCADE,
    ward TEXT NOT NULL,
    bed_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('available', 'reserved', 'occupied', 'cleaning', 'unavailable')),
    patient_id TEXT REFERENCES patients(patient_id),
    reserved_for TEXT,
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rfid_assignments (
    uid TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('patient', 'doctor', 'nurse', 'reserved')),
    entity_id TEXT,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    assigned_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS emergency_cases (
    id TEXT PRIMARY KEY,
    ambulance_id TEXT,
    patient_id TEXT REFERENCES patients(patient_id),
    hospital_id TEXT REFERENCES hospitals(id),
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    heart_rate REAL,
    spo2 REAL,
    requested_department TEXT,
    requested_bed TEXT,
    eta_minutes INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS hospital_prealerts (
    id TEXT PRIMARY KEY,
    emergency_case_id TEXT NOT NULL REFERENCES emergency_cases(id) ON DELETE CASCADE,
    hospital_id TEXT NOT NULL REFERENCES hospitals(id),
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS medicine_reservations (
    id TEXT PRIMARY KEY,
    inventory_id INTEGER NOT NULL REFERENCES pharmacy_inventory(id),
    emergency_case_id TEXT REFERENCES emergency_cases(id),
    patient_id TEXT REFERENCES patients(patient_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_updated TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patient_events (
    id TEXT PRIMARY KEY,
    patient_id TEXT REFERENCES patients(patient_id),
    hospital_id TEXT REFERENCES hospitals(id),
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_beds_hospital ON beds(hospital_id, bed_type, status);
CREATE INDEX IF NOT EXISTS idx_patient_events_patient ON patient_events(patient_id, created_at DESC);
"""


HOSPITALS = [
    ("HOSP-001", "CareGrid Central Hospital", 12.9716, 77.5946, "1 Central Care Road", "+91 80000 10001", 1, 1, 12, 7, 8, 3, 60, 24, 3, 1, 1, 5, "online"),
    ("HOSP-002", "CareGrid City Medical Centre", 12.9860, 77.6065, "22 City Medical Avenue", "+91 80000 10002", 1, 1, 8, 2, 6, 1, 44, 12, 2, 1, 1, 2, "online"),
    ("HOSP-003", "CareGrid Emergency & Trauma Centre", 12.9572, 77.6101, "7 Trauma Corridor", "+91 80000 10003", 1, 1, 16, 6, 10, 2, 36, 10, 4, 1, 1, 6, "online"),
    ("HOSP-004", "CareGrid Community Hospital", 13.0035, 77.5762, "40 Community Health Road", "+91 80000 10004", 1, 0, 6, 4, 0, 0, 32, 18, 1, 0, 1, 0, "online"),
    ("HOSP-005", "CareGrid Specialty Hospital", 12.9432, 77.5824, "5 Specialty Avenue", "+91 80000 10005", 0, 1, 4, 1, 12, 5, 40, 16, 5, 1, 1, 8, "online"),
]

DEPARTMENTS = {
    "HOSP-001": ["Emergency", "Cardiology", "Neurology", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-002": ["Emergency", "Cardiology", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-003": ["Emergency", "Cardiology", "Neurology", "Orthopaedics", "ICU", "Trauma"],
    "HOSP-004": ["Emergency", "Orthopaedics", "General Medicine", "Pediatrics"],
    "HOSP-005": ["Cardiology", "Neurology", "Orthopaedics", "ICU"],
}

MEDICINES = [
    "Adrenaline", "Insulin", "Atropine", "Dopamine", "Noradrenaline",
    "Salbutamol", "Paracetamol", "Ceftriaxone", "Aspirin", "Nitroglycerin",
    "Heparin", "Amiodarone", "Dextrose", "Normal Saline", "Ringer Lactate",
]


def init_hospital_db() -> None:
    resource_database.configure_database(DB_PATH)
    resource_database.initialize_database()
    with connect_db() as connection:
        connection.executescript(DOMAIN_SCHEMA)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(emergency_cases)")}
        if "eta_minutes" not in columns:
            connection.execute("ALTER TABLE emergency_cases ADD COLUMN eta_minutes INTEGER")


def seed_demo_data() -> dict[str, int]:
    """Insert deterministic simulation records without duplicating core rows."""
    resource_database.configure_database(DB_PATH)
    resource_counts = resource_database.seed_resource_data()
    now = utc_now()
    with connect_db() as connection:
        patients = [
            ("PATIENT-001", "Balaji", "O+", "none recorded", None, "demo placeholder", 1, now),
            ("PATIENT-002", "Akshitha", "B+", "none recorded", None, "demo placeholder", 1, now),
            ("PATIENT-003", "Lekha", "A+", "none recorded", "Smile disorder", "demo placeholder", 1, now),
        ]
        connection.executemany("INSERT OR IGNORE INTO patients VALUES(?,?,?,?,?,?,?,?)", patients)
        connection.execute("INSERT OR IGNORE INTO doctors VALUES(?,?,?,?,?)", ("DOC-001", "Hari", "Emergency Medicine", 1, now))
        connection.execute("INSERT OR IGNORE INTO nurses VALUES(?,?,?,?,?)", ("NURSE-001", "CareGrid Demo Nurse", "Emergency", 1, now))

        assignments = [
            ("D0:DA:F6:5F", "patient", "PATIENT-001"),
            ("1D:69:50:06", "patient", "PATIENT-002"),
            ("53:67:70:56", "patient", "PATIENT-003"),
            ("AA:B4:32:06", "doctor", "DOC-001"),
            ("04:06:96:04", "reserved", None),
            ("76:4D:32:06", "reserved", None),
            ("43:E7:50:06", "reserved", None),
        ]
        for uid, entity_type, entity_id in assignments:
            connection.execute(
                "INSERT OR IGNORE INTO rfid_assignments(uid,entity_type,entity_id,active,assigned_at) VALUES(?,?,?,?,?)",
                (uid, entity_type, entity_id, 1, now),
            )

        connection.execute(
            """INSERT OR IGNORE INTO patient_events
            (id,patient_id,hospital_id,event_type,severity,summary,payload_json,created_at)
            VALUES('EVENT-DEMO-001','PATIENT-001','HOSP-001','demo_record','info',
                   'Demo patient record initialized','{"demo":true}',?)""",
            (now,),
        )

        tables = [
            "beds", "patients", "doctors",
            "nurses", "rfid_assignments", "emergency_cases", "hospital_prealerts",
            "medicine_reservations", "patient_events",
        ]
        domain_counts = {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
        return {**resource_counts, **domain_counts}


def _as_bool_fields(item: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    for field in fields:
        item[field] = bool(item[field])
    return item


def _patient_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    tag = connection.execute(
        "SELECT uid FROM rfid_assignments WHERE entity_type='patient' AND entity_id=? AND active=1",
        (item["patient_id"],),
    ).fetchone()
    item["rfid_uid"] = tag["uid"] if tag else None
    item["demo_data"] = bool(item.pop("demo"))
    return item


def _hospital_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    return _as_bool_fields(item, ("emergency_enabled", "icu_available", "blood_bank_available", "oxygen_available")) | {"demo_data": True}


def _distance_km(latitude: float, longitude: float, target_latitude: float, target_longitude: float) -> float:
    radius_km = 6371.0
    lat1, lat2 = math.radians(latitude), math.radians(target_latitude)
    delta_lat = math.radians(target_latitude - latitude)
    delta_lon = math.radians(target_longitude - longitude)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _requested_department(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    return "Emergency Medicine" if normalized.lower() == "emergency" else normalized


@hospital_router.get("/patients")
def list_patients() -> dict[str, Any]:
    with connect_db() as connection:
        items = [_patient_payload(connection, row) for row in connection.execute("SELECT * FROM patients ORDER BY name")]
    return {"count": len(items), "items": items, "data_classification": "hackathon_simulation"}


@hospital_router.get("/patients/{patient_id}")
def get_patient(patient_id: str) -> dict[str, Any]:
    with connect_db() as connection:
        row = connection.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        return _patient_payload(connection, row)


@hospital_router.patch("/patients/{patient_id}")
def update_patient(patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    field_map = {"diagnosis": "condition", "condition": "condition", "allergies": "allergies"}
    changes = {field_map[key]: value for key, value in payload.items() if key in field_map}
    if not changes:
        raise HTTPException(status_code=422, detail="Only condition/diagnosis and allergies can be updated")
    changes["last_updated"] = utc_now()
    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        assignments = ",".join(f"{key}=?" for key in changes)
        connection.execute(f"UPDATE patients SET {assignments} WHERE patient_id=?", (*changes.values(), patient_id))
        row = connection.execute("SELECT * FROM patients WHERE patient_id=?", (patient_id,)).fetchone()
        return _patient_payload(connection, row)


@hospital_router.get("/patients/{patient_id}/events")
def get_patient_events(patient_id: str) -> dict[str, Any]:
    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        rows = connection.execute("SELECT * FROM patient_events WHERE patient_id=? ORDER BY created_at DESC", (patient_id,)).fetchall()
    return {"count": len(rows), "items": [dict(row) for row in rows]}


@hospital_router.post("/patients/{patient_id}/events", status_code=201)
def create_patient_event(patient_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary = str(payload.get("summary") or "").strip()
    if not summary:
        raise HTTPException(status_code=422, detail="summary is required")
    event_id = f"EVENT-{uuid.uuid4().hex[:10].upper()}"
    now = utc_now()
    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Patient not found")
        connection.execute(
            """INSERT INTO patient_events(id,patient_id,hospital_id,event_type,severity,summary,payload_json,created_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (event_id, patient_id, payload.get("hospital_id"), payload.get("event_type") or "note",
             str(payload.get("severity") or "info").lower(), summary, json.dumps(payload.get("payload") or {}), now),
        )
        row = connection.execute("SELECT * FROM patient_events WHERE id=?", (event_id,)).fetchone()
    return dict(row)


@hospital_router.get("/rfid/{uid}")
def get_rfid_assignment(uid: str) -> dict[str, Any]:
    normalized = uid.strip().upper()
    with connect_db() as connection:
        assignment = connection.execute("SELECT * FROM rfid_assignments WHERE uid=? AND active=1", (normalized,)).fetchone()
        if assignment is None:
            raise HTTPException(status_code=404, detail="Unknown RFID Tag")
        item = dict(assignment)
        entity_type, entity_id = item["entity_type"], item["entity_id"]
        if entity_type == "reserved":
            return {"uid": normalized, "known": False, "reserved": True, "status": "Reserved RFID Tag", "demo_data": True}
        table, key = {"patient": ("patients", "patient_id"), "doctor": ("doctors", "doctor_id"), "nurse": ("nurses", "nurse_id")}[entity_type]
        entity = connection.execute(f"SELECT * FROM {table} WHERE {key}=?", (entity_id,)).fetchone()
        return {
            "uid": normalized,
            "known": True,
            "reserved": False,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity": dict(entity) if entity else None,
            "status": "RFID verified",
            "demo_data": True,
        }


@hospital_router.get("/hospitals")
def list_hospitals() -> dict[str, Any]:
    items = hospital_repository.list_hospitals()
    return {
        "status": "ok", "source": "database", "simulation": True,
        "count": len(items), "hospitals": items, "items": items,
    }


@hospital_router.get("/hospitals/recommend")
def recommend_hospitals(
    department: str | None = None,
    requested_bed: str | None = None,
    medicine: str | None = None,
    icu_required: bool = False,
    emergency_required: bool = False,
    latitude: float = 12.9716,
    longitude: float = 77.5946,
) -> dict[str, Any]:
    """Compatibility ranking over database-owned resources; P0.2 will replace this."""
    department = _requested_department(department)
    bed_type = (requested_bed or "").strip().upper()
    if bed_type == "NORMAL":
        bed_type = "GENERAL"
    ranked: list[dict[str, Any]] = []
    for hospital in hospital_repository.list_hospitals():
        if hospital["status"] != "online":
            continue
        departments = hospital_repository.get_departments(hospital["id"]) or []
        beds = {item["bed_type"]: item for item in (hospital_repository.get_beds(hospital["id"]) or [])}
        medicines = hospital_repository.get_pharmacy(hospital["id"], medicine or "") or []
        department_ok = not department or any(item["name"].lower() == department.lower() and item["available"] for item in departments)
        bed_available = beds.get(bed_type, {}).get("available") if bed_type else None
        bed_ok = not bed_type or bool(bed_available)
        medicine_row = next((item for item in medicines if not medicine or item["medicine"].lower() == medicine.lower()), None)
        medicine_available = medicine_row["available"] if medicine_row else (None if not medicine else 0)
        eligible = (
            department_ok and bed_ok and (not medicine or medicine_available > 0)
            and (not icu_required or hospital["icu_beds_available"] > 0)
            and (not emergency_required or hospital["emergency_enabled"] and hospital["emergency_beds_available"] > 0)
        )
        if not eligible:
            continue
        distance = _distance_km(latitude, longitude, hospital["latitude"], hospital["longitude"])
        score = round(min(100, 50 + min(20, hospital["emergency_beds_available"] * 2) + min(15, hospital["icu_beds_available"] * 2) + max(0, 15 - distance)))
        reasons = [value for value in [department and f"{department} available", bed_type and f"{bed_type.title()} bed available", medicine and f"{medicine} stock available"] if value]
        ranked.append({
            "hospital": hospital, "score": score, "eligibility": "eligible",
            "reason": ", ".join(reasons or ["Hospital is operational with available capacity"]) + ".",
            "distance": round(distance, 1),
            "availability": {
                "requested_department": department_ok, "requested_bed": bed_available,
                "icu_beds": hospital["icu_beds_available"], "emergency_beds": hospital["emergency_beds_available"],
                "medicine": medicine_row["medicine"] if medicine_row else medicine, "medicine_quantity": medicine_available,
                "oxygen": hospital["oxygen_available"], "ventilators": hospital["ventilators_available"],
            },
        })

    ranked.sort(key=lambda item: (-item["score"], item["distance"], item["hospital"]["id"]))
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
    return {"status": "ok", "source": "database", "simulation": True, "count": len(ranked), "items": ranked}


@hospital_router.get("/hospitals/{hospital_id}")
def get_hospital(hospital_id: str) -> dict[str, Any]:
    item = hospital_repository.get_hospital(hospital_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, **item}


@hospital_router.get("/hospitals/{hospital_id}/beds")
def get_hospital_beds(hospital_id: str) -> dict[str, Any]:
    items = hospital_repository.get_beds(hospital_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, "count": len(items), "beds": items, "items": items}


@hospital_router.post("/hospitals/{hospital_id}/beds/reserve", status_code=201)
def reserve_hospital_bed(hospital_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    bed_type = str(payload.get("bed_type") or payload.get("bedType") or "EMERGENCY").strip().upper()
    if bed_type == "NORMAL":
        bed_type = "GENERAL"
    if bed_type not in {"EMERGENCY", "ICU", "GENERAL", "TRAUMA", "PEDIATRIC"}:
        raise HTTPException(status_code=422, detail="Unsupported bed_type")
    reservation_id = f"BEDRES-{uuid.uuid4().hex[:10].upper()}"
    try:
        result = hospital_repository.reserve_bed(hospital_id, bed_type)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="Hospital or bed type not found")
    return {
        "reservation_id": reservation_id,
        "reservationId": reservation_id,
        "hospital_id": hospital_id,
        "bed_id": f"{hospital_id}-{bed_type}-CAPACITY",
        "bed_type": bed_type,
        "status": "reserved",
        "available": result["available"],
        "demo_data": True,
    }


@hospital_router.get("/hospitals/{hospital_id}/departments")
def get_hospital_departments(hospital_id: str) -> dict[str, Any]:
    items = hospital_repository.get_departments(hospital_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, "count": len(items), "departments": items, "items": items}


def _pharmacy_items(query: str, hospital_id: str | None = None) -> list[dict[str, Any]]:
    if hospital_id:
        return hospital_repository.get_pharmacy(hospital_id, query) or []
    return hospital_repository.search_medicine(query)


@hospital_router.get("/pharmacy/search")
def search_pharmacy(
    query: str | None = Query(default=None, max_length=120),
    q: str | None = Query(default=None, max_length=120),
) -> dict[str, Any]:
    """Search cross-hospital stock; ``q`` remains a temporary compatibility alias."""
    term = (query if query is not None else q or "").strip()
    items = _pharmacy_items(term)
    results = [
        {
            "id": item["id"],
            "hospital_id": item["hospital_id"],
            "hospital": item["hospital"],
            "medicine": item["medicine"],
            "available": max(0, item["available_quantity"]),
            "reserved": item["reserved_quantity"],
            "reorder_level": item["reorder_level"],
            "expiry_date": item["expiry_date"],
            "status": item["status"],
            "updated": item["updated_at"],
            "demo_data": True,
        }
        for item in items
    ]
    return {
        "status": "ok",
        "source": "database",
        "simulation": True,
        "query": term,
        "count": len(results),
        "results": results,
    }


@hospital_router.get("/hospitals/{hospital_id}/pharmacy")
def get_hospital_pharmacy(hospital_id: str, q: str = Query(default="", max_length=120)) -> dict[str, Any]:
    items = hospital_repository.get_pharmacy(hospital_id, q)
    if items is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, "count": len(items), "pharmacy": items, "items": items}


@hospital_router.get("/hospitals/{hospital_id}/equipment")
def get_hospital_equipment(hospital_id: str) -> dict[str, Any]:
    items = hospital_repository.get_equipment(hospital_id)
    if items is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, "count": len(items), "equipment": items, "items": items}


@hospital_router.get("/hospitals/{hospital_id}/resources")
def get_hospital_resources(hospital_id: str) -> dict[str, Any]:
    item = hospital_repository.get_resource_summary(hospital_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Hospital not found")
    return {"status": "ok", "source": "database", "simulation": True, **item}


def _emergency_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    patient = connection.execute("SELECT name FROM patients WHERE patient_id=?", (item["patient_id"],)).fetchone() if item["patient_id"] else None
    hospital = connection.execute("SELECT name FROM hospitals WHERE id=?", (item["hospital_id"],)).fetchone() if item["hospital_id"] else None
    item["patient"] = patient["name"] if patient else None
    item["destination"] = hospital["name"] if hospital else None
    item["demo_data"] = True
    return item


@hospital_router.get("/emergency-cases")
def list_emergency_cases(limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
    with connect_db() as connection:
        rows = connection.execute("SELECT * FROM emergency_cases ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        items = [_emergency_payload(connection, row) for row in rows]
    return {"count": len(items), "items": items, "demo_data": True}


@hospital_router.post("/emergency-cases", status_code=201)
def create_emergency_case(payload: dict[str, Any]) -> dict[str, Any]:
    hospital_id = str(payload.get("hospital_id") or payload.get("hospitalId") or "").strip()
    if not hospital_id:
        raise HTTPException(status_code=422, detail="hospital_id is required")
    now = utc_now()
    case_id = str(payload.get("id") or f"CASE-{uuid.uuid4().hex[:10].upper()}")
    patient_id = payload.get("patient_id") or payload.get("patientId")
    patient_name = payload.get("patient") or payload.get("name")
    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Hospital not found")
        if not patient_id and patient_name:
            match = connection.execute("SELECT patient_id FROM patients WHERE lower(name)=lower(?)", (str(patient_name),)).fetchone()
            patient_id = match["patient_id"] if match else None
        connection.execute(
            """INSERT INTO emergency_cases
               (id,ambulance_id,patient_id,hospital_id,incident_type,severity,status,heart_rate,spo2,
                requested_department,requested_bed,eta_minutes,notes,created_at,last_updated)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (case_id, payload.get("ambulance_id") or payload.get("ambulanceId") or "AMB-108", patient_id, hospital_id,
             payload.get("incident_type") or payload.get("category") or "Emergency", payload.get("severity") or "High",
             payload.get("status") or "destination_confirmed", payload.get("heart_rate") or payload.get("heartRate"),
             payload.get("spo2"), payload.get("requested_department") or payload.get("department"),
             payload.get("requested_bed") or payload.get("bedType"), payload.get("eta"), payload.get("notes"), now, now),
        )
        row = connection.execute("SELECT * FROM emergency_cases WHERE id=?", (case_id,)).fetchone()
        return _emergency_payload(connection, row)


@hospital_router.patch("/emergency-cases/{case_id}")
def update_emergency_case(case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {"status", "heart_rate", "spo2", "notes", "hospital_id", "eta_minutes"}
    normalized = {
        ("heart_rate" if key == "heartRate" else "hospital_id" if key == "hospitalId" else "eta_minutes" if key == "eta" else key): value
        for key, value in payload.items()
    }
    changes = {key: value for key, value in normalized.items() if key in allowed}
    if not changes:
        raise HTTPException(status_code=422, detail="No supported emergency fields supplied")
    changes["last_updated"] = utc_now()
    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM emergency_cases WHERE id=?", (case_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Emergency case not found")
        assignments = ",".join(f"{key}=?" for key in changes)
        connection.execute(f"UPDATE emergency_cases SET {assignments} WHERE id=?", (*changes.values(), case_id))
        row = connection.execute("SELECT * FROM emergency_cases WHERE id=?", (case_id,)).fetchone()
        return _emergency_payload(connection, row)


def _prealert_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["payload"] = json.loads(item.pop("payload_json"))
    item["delivery_status"] = "Delivered" if item["status"] == "sent" else item["status"].title()
    item["demo_data"] = True
    return item


@hospital_router.post("/prealerts", status_code=201)
def create_prealert(payload: dict[str, Any]) -> dict[str, Any]:
    hospital_id = str(payload.get("hospital_id") or payload.get("hospitalId") or "").strip()
    if not hospital_id:
        raise HTTPException(status_code=422, detail="hospital_id is required")
    patient_id = payload.get("patient_id") or payload.get("patientId")
    patient_name = payload.get("patient") or payload.get("patient_name")
    vitals = payload.get("vitals") if isinstance(payload.get("vitals"), dict) else {}
    heart_rate = payload.get("heart_rate", vitals.get("heartRate", vitals.get("heart_rate")))
    spo2 = payload.get("spo2", vitals.get("spo2"))
    case_id = str(payload.get("case_id") or payload.get("caseId") or f"CASE-{uuid.uuid4().hex[:10].upper()}")
    prealert_id = f"PRE-{uuid.uuid4().hex[:10].upper()}"
    now = utc_now()

    with connect_db() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Hospital not found")
        if not patient_id and patient_name:
            match = connection.execute("SELECT patient_id FROM patients WHERE lower(name)=lower(?)", (str(patient_name),)).fetchone()
            patient_id = match["patient_id"] if match else None
        if patient_id and connection.execute("SELECT 1 FROM patients WHERE patient_id=?", (patient_id,)).fetchone() is None:
            raise HTTPException(status_code=404, detail="Patient not found")

        incident = str(payload.get("incident") or payload.get("incident_type") or payload.get("category") or "Emergency")
        severity = str(payload.get("severity") or "High")
        department = payload.get("required_department") or payload.get("department")
        requested_bed = payload.get("required_bed") or payload.get("requested_bed") or payload.get("bedType")
        notes = payload.get("notes")
        existing_case = connection.execute("SELECT 1 FROM emergency_cases WHERE id=?", (case_id,)).fetchone()
        if existing_case:
            connection.execute(
                """UPDATE emergency_cases SET hospital_id=?,patient_id=COALESCE(?,patient_id),status='prealert_sent',
                   heart_rate=COALESCE(?,heart_rate),spo2=COALESCE(?,spo2),requested_department=COALESCE(?,requested_department),
                   requested_bed=COALESCE(?,requested_bed),last_updated=? WHERE id=?""",
                (hospital_id, patient_id, heart_rate, spo2, department, requested_bed, now, case_id),
            )
        else:
            connection.execute(
                """INSERT INTO emergency_cases
                   (id,ambulance_id,patient_id,hospital_id,incident_type,severity,status,heart_rate,spo2,
                    requested_department,requested_bed,eta_minutes,notes,created_at,last_updated)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (case_id, payload.get("ambulance_id") or payload.get("ambulanceId"), patient_id, hospital_id,
                 incident, severity, "prealert_sent", heart_rate, spo2, department, requested_bed,
                 payload.get("eta"), notes, now, now),
            )
        stored_payload = {
            **payload,
            "case_id": case_id,
            "patient_id": patient_id,
            "patient": patient_name,
            "incident": incident,
            "severity": severity,
            "heart_rate": heart_rate,
            "spo2": spo2,
            "required_department": department,
            "required_bed": requested_bed,
            "medicine": payload.get("medicine"),
            "selected_hospital": hospital_id,
            "timestamp": now,
        }
        connection.execute(
            "INSERT INTO hospital_prealerts(id,emergency_case_id,hospital_id,payload_json,status,created_at) VALUES(?,?,?,?,?,?)",
            (prealert_id, case_id, hospital_id, json.dumps(stored_payload), "sent", now),
        )
        if patient_id:
            connection.execute(
                """INSERT INTO patient_events(id,patient_id,hospital_id,event_type,severity,summary,payload_json,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (f"EVENT-{uuid.uuid4().hex[:10].upper()}", patient_id, hospital_id, "emergency_prealert", severity.lower(),
                 f"Emergency pre-alert sent to {hospital_id}", json.dumps(stored_payload), now),
            )
        row = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
    result = _prealert_payload(row)
    result["deliveryStatus"] = result["delivery_status"]
    result["deliveredAt"] = now
    return result


@hospital_router.get("/prealerts")
def list_prealerts(limit: int = Query(default=50, ge=1, le=100)) -> dict[str, Any]:
    with connect_db() as connection:
        rows = connection.execute("SELECT * FROM hospital_prealerts ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return {"count": len(rows), "items": [_prealert_payload(row) for row in rows], "demo_data": True}


@hospital_router.get("/prealerts/{prealert_id}")
def get_prealert(prealert_id: str) -> dict[str, Any]:
    with connect_db() as connection:
        row = connection.execute("SELECT * FROM hospital_prealerts WHERE id=?", (prealert_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Pre-alert not found")
    return _prealert_payload(row)
