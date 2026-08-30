from __future__ import annotations

from typing import Any

from .. import database


def _available(total: int, occupied_or_reserved: int, reserved: int = 0) -> int:
    return max(0, int(total) - int(occupied_or_reserved) - int(reserved))


def _bed_rows(connection, hospital_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM bed_capacity WHERE hospital_id=? ORDER BY bed_type", (hospital_id,)
    ).fetchall()
    return [
        {**dict(row), "available": _available(row["total"], row["occupied"], row["reserved"]), "simulation": True}
        for row in rows
    ]


def _hospital_payload(connection, row) -> dict[str, Any]:
    item = dict(row)
    beds = {bed["bed_type"]: bed for bed in _bed_rows(connection, item["id"])}
    equipment = {
        entry["equipment_name"]: dict(entry)
        for entry in connection.execute("SELECT * FROM equipment_inventory WHERE hospital_id=?", (item["id"],))
    }
    resources = {
        entry["resource_name"]: dict(entry)
        for entry in connection.execute("SELECT * FROM hospital_resources WHERE hospital_id=?", (item["id"],))
    }

    def bed_value(bed_type: str, field: str) -> int:
        return int(beds.get(bed_type, {}).get(field, 0))

    ventilators = equipment.get("Ventilator", {})
    oxygen = equipment.get("Oxygen Supply", {})
    blood_bank = resources.get("Blood Bank", {})
    operating_rooms = resources.get("Operating Room", {})
    item.update({
        "emergency_enabled": bool(item["emergency_enabled"]),
        "trauma_enabled": bool(item["trauma_enabled"]),
        "is_demo": bool(item["is_demo"]),
        "demo_data": bool(item["is_demo"]),
        "simulation": bool(item["is_demo"]),
        "emergency_beds_total": bed_value("EMERGENCY", "total"),
        "emergency_beds_available": bed_value("EMERGENCY", "available"),
        "icu_beds_total": bed_value("ICU", "total"),
        "icu_beds_available": bed_value("ICU", "available"),
        "normal_beds_total": bed_value("GENERAL", "total"),
        "normal_beds_available": bed_value("GENERAL", "available"),
        "icu_available": bed_value("ICU", "available") > 0,
        "operating_rooms_available": int(operating_rooms.get("quantity") or 0),
        "blood_bank_available": bool(blood_bank.get("available", 0)),
        "oxygen_available": int(oxygen.get("available", 0)) > 0,
        "ventilators_available": int(ventilators.get("available", 0)),
        "last_updated": item["updated_at"],
    })
    return item


def list_hospitals() -> list[dict[str, Any]]:
    with database.connect() as connection:
        return [_hospital_payload(connection, row) for row in connection.execute("SELECT * FROM hospitals ORDER BY id")]


def get_hospital(hospital_id: str) -> dict[str, Any] | None:
    with database.connect() as connection:
        row = connection.execute("SELECT * FROM hospitals WHERE id=?", (hospital_id,)).fetchone()
        return _hospital_payload(connection, row) if row else None


def get_departments(hospital_id: str) -> list[dict[str, Any]] | None:
    with database.connect() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            return None
        rows = connection.execute("SELECT * FROM departments WHERE hospital_id=? ORDER BY name", (hospital_id,)).fetchall()
        return [
            {**dict(row), "available": row["status"].lower() in {"available", "online", "open"}, "simulation": True}
            for row in rows
        ]


def get_beds(hospital_id: str) -> list[dict[str, Any]] | None:
    with database.connect() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            return None
        return _bed_rows(connection, hospital_id)


def get_equipment(hospital_id: str) -> list[dict[str, Any]] | None:
    with database.connect() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            return None
        rows = connection.execute("SELECT * FROM equipment_inventory WHERE hospital_id=? ORDER BY equipment_name", (hospital_id,)).fetchall()
        return [{**dict(row), "operational": bool(row["operational"]), "simulation": True} for row in rows]


def get_pharmacy(hospital_id: str, query: str = "") -> list[dict[str, Any]] | None:
    with database.connect() as connection:
        if connection.execute("SELECT 1 FROM hospitals WHERE id=?", (hospital_id,)).fetchone() is None:
            return None
        term = f"{query.strip().lower()}%"
        rows = connection.execute(
            """SELECT p.*, h.name AS hospital FROM pharmacy_inventory p
               JOIN hospitals h ON h.id=p.hospital_id
               WHERE p.hospital_id=? AND lower(p.medicine_name) LIKE ?
               ORDER BY p.medicine_name""",
            (hospital_id, term),
        ).fetchall()
        return [_pharmacy_payload(row) for row in rows]


def _pharmacy_payload(row) -> dict[str, Any]:
    item = dict(row)
    available = max(0, int(item["total_quantity"]) - int(item["reserved_quantity"]))
    return {
        **item,
        "medicine": item["medicine_name"],
        "quantity": item["total_quantity"],
        "available_quantity": available,
        "available": available,
        "reserved": item["reserved_quantity"],
        "updated": item["updated_at"],
        "demo_data": True,
        "simulation": True,
    }


def search_medicine(query: str) -> list[dict[str, Any]]:
    term = f"{query.strip().lower()}%"
    with database.connect() as connection:
        rows = connection.execute(
            """SELECT p.*, h.name AS hospital FROM pharmacy_inventory p
               JOIN hospitals h ON h.id=p.hospital_id
               WHERE lower(p.medicine_name) LIKE ?
               ORDER BY p.medicine_name, h.id""",
            (term,),
        ).fetchall()
        return [_pharmacy_payload(row) for row in rows]


def get_resource_summary(hospital_id: str) -> dict[str, Any] | None:
    hospital = get_hospital(hospital_id)
    if hospital is None:
        return None
    beds = get_beds(hospital_id) or []
    departments = get_departments(hospital_id) or []
    equipment = get_equipment(hospital_id) or []
    with database.connect() as connection:
        resources = [
            {**dict(row), "available": bool(row["available"]), "simulation": True}
            for row in connection.execute(
                "SELECT * FROM hospital_resources WHERE hospital_id=? ORDER BY resource_type, resource_name", (hospital_id,)
            )
        ]
    timestamps = [hospital["updated_at"]]
    timestamps.extend(item["updated_at"] for item in beds + departments + equipment + resources)
    return {
        "hospital": hospital,
        "beds": beds,
        "departments": departments,
        "equipment": equipment,
        "critical_resources": resources,
        "last_updated": max(timestamps),
    }


def reserve_bed(hospital_id: str, bed_type: str) -> dict[str, Any] | None:
    normalized = bed_type.strip().upper()
    if normalized == "NORMAL":
        normalized = "GENERAL"
    with database.connect() as connection:
        row = connection.execute(
            "SELECT * FROM bed_capacity WHERE hospital_id=? AND bed_type=?", (hospital_id, normalized)
        ).fetchone()
        if row is None:
            return None
        available = _available(row["total"], row["occupied"], row["reserved"])
        if available <= 0:
            raise ValueError(f"No {normalized.title()} bed is currently available")
        updated = database.utc_now()
        cursor = connection.execute(
            """UPDATE bed_capacity SET reserved=reserved+1, updated_at=?
               WHERE id=? AND occupied+reserved<total""",
            (updated, row["id"]),
        )
        if cursor.rowcount != 1:
            raise ValueError(f"No {normalized.title()} bed is currently available")
        return {"bed_type": normalized, "available": available - 1, "updated_at": updated}
