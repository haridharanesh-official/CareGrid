from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("CAREGRID_DB_PATH", str(BASE_DIR / "data" / "caregrid.db")))


def configure_database(path: Path | str) -> None:
    global DB_PATH
    DB_PATH = Path(path)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


RESOURCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS hospitals (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT UNIQUE,
    address TEXT,
    latitude REAL,
    longitude REAL,
    phone TEXT,
    status TEXT NOT NULL,
    emergency_enabled INTEGER NOT NULL DEFAULT 1 CHECK (emergency_enabled IN (0, 1)),
    trauma_enabled INTEGER NOT NULL DEFAULT 0 CHECK (trauma_enabled IN (0, 1)),
    is_demo INTEGER NOT NULL DEFAULT 1 CHECK (is_demo IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    doctors_on_duty INTEGER NOT NULL DEFAULT 0 CHECK (doctors_on_duty >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    UNIQUE (hospital_id, name)
);

CREATE TABLE IF NOT EXISTS bed_capacity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    bed_type TEXT NOT NULL,
    total INTEGER NOT NULL CHECK (total >= 0),
    occupied INTEGER NOT NULL DEFAULT 0 CHECK (occupied >= 0),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    UNIQUE (hospital_id, bed_type),
    CHECK (occupied + reserved <= total)
);

CREATE TABLE IF NOT EXISTS equipment_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    equipment_name TEXT NOT NULL,
    total INTEGER NOT NULL CHECK (total >= 0),
    available INTEGER NOT NULL CHECK (available >= 0),
    reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    operational INTEGER NOT NULL DEFAULT 1 CHECK (operational IN (0, 1)),
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    UNIQUE (hospital_id, equipment_name),
    CHECK (available + reserved <= total)
);

CREATE TABLE IF NOT EXISTS pharmacy_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    medicine_name TEXT NOT NULL,
    total_quantity INTEGER NOT NULL CHECK (total_quantity >= 0),
    reserved_quantity INTEGER NOT NULL DEFAULT 0 CHECK (reserved_quantity >= 0),
    reorder_level INTEGER NOT NULL DEFAULT 5 CHECK (reorder_level >= 0),
    expiry_date TEXT,
    status TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    UNIQUE (hospital_id, medicine_name),
    CHECK (reserved_quantity <= total_quantity)
);

CREATE TABLE IF NOT EXISTS hospital_resources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hospital_id TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    available INTEGER NOT NULL DEFAULT 1 CHECK (available >= 0),
    quantity INTEGER CHECK (quantity IS NULL OR quantity >= 0),
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE,
    UNIQUE (hospital_id, resource_type, resource_name)
);

CREATE INDEX IF NOT EXISTS idx_resource_departments_hospital ON departments(hospital_id);
CREATE INDEX IF NOT EXISTS idx_bed_capacity_hospital ON bed_capacity(hospital_id, bed_type);
CREATE INDEX IF NOT EXISTS idx_equipment_hospital ON equipment_inventory(hospital_id);
CREATE INDEX IF NOT EXISTS idx_resource_pharmacy_medicine ON pharmacy_inventory(medicine_name);
CREATE INDEX IF NOT EXISTS idx_hospital_resources_hospital ON hospital_resources(hospital_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_hospitals_code_unique ON hospitals(code);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pharmacy_hospital_medicine_unique ON pharmacy_inventory(hospital_id, medicine_name);

CREATE TABLE IF NOT EXISTS hospital_nodes (
    hospital_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL DEFAULT 'simulated_hospital',
    advertised_online INTEGER NOT NULL DEFAULT 0 CHECK (advertised_online IN (0, 1)),
    last_seen TEXT,
    age_seconds REAL,
    connection_status TEXT NOT NULL DEFAULT 'OFFLINE'
        CHECK (connection_status IN ('LIVE', 'STALE', 'OFFLINE')),
    resource_version INTEGER NOT NULL DEFAULT 0 CHECK (resource_version >= 0),
    last_status_sequence INTEGER NOT NULL DEFAULT 0 CHECK (last_status_sequence >= 0),
    resource_updated_at TEXT,
    status_updated_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hospital_nodes_status
ON hospital_nodes(connection_status, last_seen);
"""


HOSPITALS = [
    ("HOSP-001", "Ganga Hospital", "GANGA", "313 Mettupalayam Road, Coimbatore", 11.0224, 76.9558, "+91 422 248 5000", "online", 1, 1),
    ("HOSP-002", "PSG Hospitals", "PSG", "Peelamedu, Coimbatore", 11.0183, 77.0074, "+91 422 257 0170", "online", 1, 1),
    ("HOSP-003", "KMCH", "KMCH", "Avinashi Road, Coimbatore", 11.0410, 77.0402, "+91 422 432 3800", "online", 1, 1),
    ("HOSP-004", "Sri Ramakrishna Hospital", "SRH", "Sidhapudur, Coimbatore", 11.0236, 76.9745, "+91 422 450 0000", "online", 1, 0),
    ("HOSP-005", "Government Medical College Hospital", "GMCH", "Trichy Road, Coimbatore", 10.9955, 76.9702, "+91 422 230 1393", "online", 1, 1),
]

DEPARTMENTS = {
    "HOSP-001": ["Emergency Medicine", "Cardiology", "Neurology", "Trauma", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-002": ["Emergency Medicine", "Cardiology", "Neurology", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-003": ["Emergency Medicine", "Cardiology", "Neurology", "Trauma", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-004": ["Emergency Medicine", "Cardiology", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
    "HOSP-005": ["Emergency Medicine", "Neurology", "Trauma", "Orthopaedics", "General Medicine", "Pediatrics", "ICU"],
}

BED_PROFILES = {
    "HOSP-001": {"EMERGENCY": (12, 4, 2), "ICU": (8, 4, 1), "GENERAL": (60, 31, 5), "TRAUMA": (6, 2, 1), "PEDIATRIC": (14, 7, 1)},
    "HOSP-002": {"EMERGENCY": (10, 5, 1), "ICU": (10, 4, 1), "GENERAL": (72, 46, 4), "TRAUMA": (4, 2, 1), "PEDIATRIC": (18, 9, 2)},
    "HOSP-003": {"EMERGENCY": (16, 6, 2), "ICU": (14, 5, 2), "GENERAL": (80, 51, 6), "TRAUMA": (12, 5, 1), "PEDIATRIC": (20, 13, 2)},
    "HOSP-004": {"EMERGENCY": (8, 5, 1), "ICU": (6, 3, 1), "GENERAL": (48, 30, 4), "TRAUMA": (2, 2, 0), "PEDIATRIC": (12, 7, 1)},
    "HOSP-005": {"EMERGENCY": (14, 9, 2), "ICU": (6, 4, 1), "GENERAL": (96, 68, 8), "TRAUMA": (8, 4, 1), "PEDIATRIC": (24, 15, 3)},
}

EQUIPMENT_PROFILES = {
    "HOSP-001": {"Ventilator": (8, 4, 1), "Defibrillator": (5, 3, 0), "Oxygen Supply": (20, 16, 2), "ECG": (7, 5, 1), "Infusion Pump": (24, 18, 2)},
    "HOSP-002": {"Ventilator": (10, 6, 1), "Defibrillator": (6, 4, 1), "Oxygen Supply": (24, 18, 2), "ECG": (9, 6, 1), "Infusion Pump": (30, 21, 4)},
    "HOSP-003": {"Ventilator": (14, 9, 1), "Defibrillator": (8, 6, 0), "Oxygen Supply": (30, 25, 2), "ECG": (11, 8, 1), "Infusion Pump": (38, 29, 3)},
    "HOSP-004": {"Ventilator": (6, 3, 1), "Defibrillator": (4, 2, 1), "Oxygen Supply": (16, 11, 2), "ECG": (5, 3, 1), "Infusion Pump": (18, 12, 2)},
    "HOSP-005": {"Ventilator": (9, 5, 2), "Defibrillator": (7, 4, 1), "Oxygen Supply": (28, 20, 3), "ECG": (8, 5, 1), "Infusion Pump": (32, 23, 4)},
}

MEDICINES = [
    "Adrenaline", "Insulin", "Atropine", "Dopamine", "Noradrenaline",
    "Salbutamol", "Paracetamol", "Ceftriaxone", "Aspirin", "Nitroglycerin",
    "Heparin", "Amiodarone", "Dextrose", "Normal Saline", "Ringer Lactate",
]


def validate_bed_state(total: int, occupied: int, reserved: int) -> None:
    if min(total, occupied, reserved) < 0:
        raise ValueError("Bed quantities cannot be negative")
    if occupied + reserved > total:
        raise ValueError("Occupied and reserved beds cannot exceed total beds")


def validate_equipment_state(total: int, available: int, reserved: int) -> None:
    if min(total, available, reserved) < 0:
        raise ValueError("Equipment quantities cannot be negative")
    if available + reserved > total:
        raise ValueError("Available and reserved equipment cannot exceed total")


def validate_pharmacy_state(total: int, reserved: int) -> None:
    if total < 0 or reserved < 0:
        raise ValueError("Medicine quantities cannot be negative")
    if reserved > total:
        raise ValueError("Reserved medicine cannot exceed total quantity")


def _columns(connection: sqlite3.Connection, table: str) -> dict[str, sqlite3.Row]:
    return {row["name"]: row for row in connection.execute(f"PRAGMA table_info({table})")}


def _add_legacy_columns(connection: sqlite3.Connection) -> None:
    additions = {
        "hospitals": {
            "code": "TEXT", "trauma_enabled": "INTEGER NOT NULL DEFAULT 0", "is_demo": "INTEGER NOT NULL DEFAULT 1",
            "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
        },
        "departments": {
            "status": "TEXT NOT NULL DEFAULT 'available'", "doctors_on_duty": "INTEGER NOT NULL DEFAULT 0",
            "created_at": "TEXT NOT NULL DEFAULT ''", "updated_at": "TEXT NOT NULL DEFAULT ''",
        },
        "pharmacy_inventory": {
            "medicine_name": "TEXT", "total_quantity": "INTEGER", "status": "TEXT NOT NULL DEFAULT 'available'",
            "updated_at": "TEXT NOT NULL DEFAULT ''",
        },
    }
    for table, definitions in additions.items():
        existing = _columns(connection, table)
        if not existing:
            continue
        for name, definition in definitions.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
    hospital_columns = _columns(connection, "hospitals")
    if hospital_columns and "last_updated" in hospital_columns:
        connection.execute("UPDATE hospitals SET code=COALESCE(code,id), created_at=COALESCE(NULLIF(created_at,''),last_updated), updated_at=COALESCE(NULLIF(updated_at,''),last_updated)")
    department_columns = _columns(connection, "departments")
    if department_columns and "available" in department_columns:
        connection.execute("UPDATE departments SET status=CASE WHEN available=1 THEN 'available' ELSE 'offline' END, created_at=COALESCE(NULLIF(created_at,''),?), updated_at=COALESCE(NULLIF(updated_at,''),?)", (utc_now(), utc_now()))
    pharmacy_columns = _columns(connection, "pharmacy_inventory")
    if pharmacy_columns and "medicine" in pharmacy_columns:
        connection.execute("UPDATE pharmacy_inventory SET medicine_name=COALESCE(medicine_name,medicine), total_quantity=COALESCE(total_quantity,quantity), updated_at=COALESCE(NULLIF(updated_at,''),last_updated)")


def initialize_database() -> None:
    with connect() as connection:
        _add_legacy_columns(connection)
        connection.executescript(RESOURCE_SCHEMA)
        _add_legacy_columns(connection)


def _upsert(connection: sqlite3.Connection, table: str, values: dict[str, Any], conflict: str) -> None:
    existing = _columns(connection, table)
    filtered = {key: value for key, value in values.items() if key in existing}
    columns = ", ".join(filtered)
    placeholders = ", ".join("?" for _ in filtered)
    updates = ", ".join(f"{key}=excluded.{key}" for key in filtered if key not in conflict.split(","))
    connection.execute(
        f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) ON CONFLICT({conflict}) DO UPDATE SET {updates}",
        tuple(filtered.values()),
    )


def upsert_record(connection: sqlite3.Connection, table: str, values: dict[str, Any], conflict: str) -> None:
    """Upsert a schema-compatible record, including migrated legacy tables."""
    _upsert(connection, table, values, conflict)


def seed_resource_data() -> dict[str, int]:
    now = utc_now()
    expiry_base = date.today() + timedelta(days=240)
    with connect() as connection:
        hospital_columns = _columns(connection, "hospitals")
        for index, hospital in enumerate(HOSPITALS, 1):
            hospital_id, name, code, address, latitude, longitude, phone, status, emergency_enabled, trauma_enabled = hospital
            beds = BED_PROFILES[hospital_id]
            equipment = EQUIPMENT_PROFILES[hospital_id]
            values = {
                "id": hospital_id, "name": name, "code": code, "address": address, "latitude": latitude,
                "longitude": longitude, "phone": phone, "status": status, "emergency_enabled": emergency_enabled,
                "trauma_enabled": trauma_enabled, "is_demo": 1, "created_at": now, "updated_at": now,
                "icu_available": int(beds["ICU"][0] - beds["ICU"][1] - beds["ICU"][2] > 0),
                "emergency_beds_total": beds["EMERGENCY"][0], "emergency_beds_available": beds["EMERGENCY"][0] - beds["EMERGENCY"][1] - beds["EMERGENCY"][2],
                "icu_beds_total": beds["ICU"][0], "icu_beds_available": beds["ICU"][0] - beds["ICU"][1] - beds["ICU"][2],
                "normal_beds_total": beds["GENERAL"][0], "normal_beds_available": beds["GENERAL"][0] - beds["GENERAL"][1] - beds["GENERAL"][2],
                "operating_rooms_available": max(1, index % 5), "blood_bank_available": int(index != 4),
                "oxygen_available": 1, "ventilators_available": equipment["Ventilator"][1], "last_updated": now,
            }
            _upsert(connection, "hospitals", values, "id")

        department_columns = _columns(connection, "departments")
        for hospital_id, names in DEPARTMENTS.items():
            for index, name in enumerate(names, 1):
                values = {
                    "hospital_id": hospital_id, "name": name, "status": "available",
                    "doctors_on_duty": (index + int(hospital_id[-1])) % 5 + 1, "created_at": now, "updated_at": now,
                    "available": 1,
                }
                if department_columns["id"]["type"].upper().startswith("TEXT"):
                    values["id"] = f"DEPT-{hospital_id[-3:]}-{index:02d}"
                _upsert(connection, "departments", values, "hospital_id,name")

        for hospital_id, profile in BED_PROFILES.items():
            for bed_type, (total, occupied, reserved) in profile.items():
                validate_bed_state(total, occupied, reserved)
                _upsert(connection, "bed_capacity", {
                    "hospital_id": hospital_id, "bed_type": bed_type, "total": total, "occupied": occupied,
                    "reserved": reserved, "status": "available" if total - occupied - reserved > 0 else "full", "updated_at": now,
                }, "hospital_id,bed_type")

        for hospital_id, profile in EQUIPMENT_PROFILES.items():
            for equipment_name, (total, available, reserved) in profile.items():
                validate_equipment_state(total, available, reserved)
                _upsert(connection, "equipment_inventory", {
                    "hospital_id": hospital_id, "equipment_name": equipment_name, "total": total,
                    "available": available, "reserved": reserved, "operational": 1, "updated_at": now,
                }, "hospital_id,equipment_name")

        pharmacy_columns = _columns(connection, "pharmacy_inventory")
        for hospital_index, hospital in enumerate(HOSPITALS, 1):
            hospital_id = hospital[0]
            for medicine_index, medicine in enumerate(MEDICINES, 1):
                total = ((hospital_index * 17 + medicine_index * 11) % 66) + 8
                if medicine == "Adrenaline":
                    total = [20, 15, 28, 9, 14][hospital_index - 1]
                reserved = min(total, (hospital_index + medicine_index) % 4)
                validate_pharmacy_state(total, reserved)
                available = total - reserved
                values = {
                    "hospital_id": hospital_id, "medicine_name": medicine, "total_quantity": total,
                    "reserved_quantity": reserved, "reorder_level": 8,
                    "expiry_date": str(expiry_base + timedelta(days=medicine_index * 4)),
                    "status": "out" if available == 0 else "low" if available <= 8 else "available", "updated_at": now,
                    "medicine": medicine, "quantity": total, "last_updated": now,
                }
                if pharmacy_columns["id"]["type"].upper().startswith("TEXT"):
                    values["id"] = f"MED-{hospital_index:02d}-{medicine_index:03d}"
                _upsert(connection, "pharmacy_inventory", values, "hospital_id,medicine_name")

        resources = {
            "HOSP-001": [("critical", "Blood Bank", 1, 1), ("facility", "Operating Room", 1, 3)],
            "HOSP-002": [("critical", "Blood Bank", 1, 1), ("facility", "Operating Room", 1, 4)],
            "HOSP-003": [("critical", "Blood Bank", 1, 1), ("facility", "Operating Room", 1, 5)],
            "HOSP-004": [("critical", "Blood Bank", 0, 0), ("facility", "Operating Room", 1, 2)],
            "HOSP-005": [("critical", "Blood Bank", 1, 1), ("facility", "Operating Room", 1, 4)],
        }
        for hospital_id, items in resources.items():
            for resource_type, resource_name, available, quantity in items:
                _upsert(connection, "hospital_resources", {
                    "hospital_id": hospital_id, "resource_type": resource_type, "resource_name": resource_name,
                    "available": available, "quantity": quantity, "updated_at": now,
                }, "hospital_id,resource_type,resource_name")

        tables = ["hospitals", "departments", "bed_capacity", "equipment_inventory", "pharmacy_inventory", "hospital_resources"]
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
