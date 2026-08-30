from __future__ import annotations

import math
from typing import Any

from ..repositories import hospital_repository


ALGORITHM_VERSION = "p0.2"
DEFAULT_ORIGIN = (11.0168, 76.9558)  # Coimbatore demo origin when no ambulance GPS is supplied.
SCORE_WEIGHTS = {
    "distance": 35,
    "requested_bed": 25,
    "icu_readiness": 15,
    "medicine": 10,
    "department": 10,
    "emergency_readiness": 5,
}


def _distance_km(latitude: float, longitude: float, target_latitude: float, target_longitude: float) -> float:
    radius_km = 6371.0
    lat1, lat2 = math.radians(latitude), math.radians(target_latitude)
    delta_lat = math.radians(target_latitude - latitude)
    delta_lon = math.radians(target_longitude - longitude)
    value = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return radius_km * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _normalize_department(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    return "Emergency Medicine" if normalized.lower() == "emergency" else normalized


def _normalize_bed_type(value: str | None) -> str | None:
    normalized = (value or "").strip().upper()
    if not normalized:
        return None
    return "GENERAL" if normalized == "NORMAL" else normalized


def _score_component(value: float, weight: int) -> dict[str, float | int]:
    normalized = round(max(0.0, min(100.0, value)), 1)
    return {
        "normalized": normalized,
        "weight": weight,
        "points": round(normalized * weight / 100, 1),
    }


def _evaluate_hospital(
    hospital: dict[str, Any],
    *,
    department: str | None,
    bed_type: str | None,
    medicine: str | None,
    icu_required: bool,
    emergency_required: bool,
    latitude: float,
    longitude: float,
) -> dict[str, Any]:
    departments = hospital_repository.get_departments(hospital["id"]) or []
    beds = {item["bed_type"]: item for item in (hospital_repository.get_beds(hospital["id"]) or [])}
    equipment = {item["equipment_name"]: item for item in (hospital_repository.get_equipment(hospital["id"]) or [])}
    medicine_rows = hospital_repository.get_pharmacy(hospital["id"], medicine or "") or []

    department_row = next(
        (item for item in departments if department and item["name"].lower() == department.lower()),
        None,
    )
    requested_bed = beds.get(bed_type) if bed_type else None
    medicine_row = next(
        (item for item in medicine_rows if medicine and item["medicine"].lower() == medicine.lower()),
        None,
    )
    icu_beds = beds.get("ICU", {})
    emergency_beds = beds.get("EMERGENCY", {})
    oxygen = equipment.get("Oxygen Supply", {})
    ventilators = equipment.get("Ventilator", {})

    department_available = department is None or bool(department_row and department_row["available"])
    requested_bed_available = None if bed_type is None else int((requested_bed or {}).get("available", 0))
    medicine_available = None if medicine is None else int((medicine_row or {}).get("available_quantity", 0))
    icu_available = int(icu_beds.get("available", 0))
    emergency_available = int(emergency_beds.get("available", 0))

    rejection_reasons: list[str] = []
    if hospital["status"].lower() != "online":
        rejection_reasons.append("Hospital is not currently operational")
    if emergency_required and (not hospital["emergency_enabled"] or emergency_available <= 0):
        rejection_reasons.append("Emergency service or emergency bed capacity is unavailable")
    if not department_available:
        rejection_reasons.append(f"Required department {department} is unavailable")
    if bed_type and requested_bed_available <= 0:
        rejection_reasons.append(f"No {bed_type.title()} bed is available")
    if medicine and medicine_available <= 0:
        rejection_reasons.append(f"Required medicine {medicine} is unavailable")
    if icu_required and icu_available <= 0:
        rejection_reasons.append("No ICU bed is available")

    distance = _distance_km(latitude, longitude, hospital["latitude"], hospital["longitude"])
    eta_minutes = max(3, round(distance * 1.8 + 4))
    availability = {
        "requested_department": department_available,
        "requested_department_name": department,
        "requested_bed": requested_bed_available,
        "requested_bed_type": bed_type,
        "icu_beds": icu_available,
        "emergency_beds": emergency_available,
        "medicine": medicine_row["medicine"] if medicine_row else medicine,
        "medicine_quantity": medicine_available,
        "oxygen": int(oxygen.get("available", 0)),
        "ventilators": int(ventilators.get("available", 0)),
    }
    base = {
        "hospital": hospital,
        "eligibility": "rejected" if rejection_reasons else "eligible",
        "distance": round(distance, 1),
        "eta": eta_minutes,
        "eta_minutes": eta_minutes,
        "availability": availability,
        "rejection_reasons": rejection_reasons,
    }
    if rejection_reasons:
        return {
            **base,
            "score": 0,
            "match_score": 0,
            "score_breakdown": {},
            "reason": "; ".join(rejection_reasons) + ".",
        }

    bed_score = 100 if bed_type is None else min(100, requested_bed_available * 12.5)
    icu_score = min(100, icu_available * 20)
    medicine_score = 100 if medicine is None else min(100, medicine_available * 5)
    emergency_score = min(100, emergency_available * 12.5) if hospital["emergency_enabled"] else 0
    breakdown = {
        "distance": _score_component(max(0, 100 - distance * 5), SCORE_WEIGHTS["distance"]),
        "requested_bed": _score_component(bed_score, SCORE_WEIGHTS["requested_bed"]),
        "icu_readiness": _score_component(icu_score, SCORE_WEIGHTS["icu_readiness"]),
        "medicine": _score_component(medicine_score, SCORE_WEIGHTS["medicine"]),
        "department": _score_component(100, SCORE_WEIGHTS["department"]),
        "emergency_readiness": _score_component(emergency_score, SCORE_WEIGHTS["emergency_readiness"]),
    }
    score = round(sum(component["points"] for component in breakdown.values()))
    capability_parts = []
    if department:
        capability_parts.append(f"{department} is available")
    if bed_type:
        capability_parts.append(f"{requested_bed_available} {bed_type.title()} beds are available")
    if medicine:
        capability_parts.append(f"{medicine_available} units of {medicine} are available")
    capability_parts.append(f"estimated travel is {round(distance, 1)} km / {eta_minutes} min")
    return {
        **base,
        "score": score,
        "match_score": score,
        "score_breakdown": breakdown,
        "reason": f"{hospital['name']} is suitable because " + ", ".join(capability_parts) + ".",
    }


def recommend_hospitals(
    *,
    department: str | None = None,
    requested_bed: str | None = None,
    medicine: str | None = None,
    icu_required: bool = False,
    emergency_required: bool = False,
    latitude: float | None = None,
    longitude: float | None = None,
) -> dict[str, Any]:
    if (latitude is None) != (longitude is None):
        raise ValueError("latitude and longitude must be supplied together")
    origin_latitude, origin_longitude = DEFAULT_ORIGIN if latitude is None else (latitude, longitude)
    normalized_department = _normalize_department(department)
    normalized_bed = _normalize_bed_type(requested_bed)
    normalized_medicine = (medicine or "").strip() or None

    evaluations = [
        _evaluate_hospital(
            hospital,
            department=normalized_department,
            bed_type=normalized_bed,
            medicine=normalized_medicine,
            icu_required=icu_required,
            emergency_required=emergency_required,
            latitude=origin_latitude,
            longitude=origin_longitude,
        )
        for hospital in hospital_repository.list_hospitals()
    ]
    eligible = [item for item in evaluations if item["eligibility"] == "eligible"]
    rejected = [item for item in evaluations if item["eligibility"] == "rejected"]
    eligible.sort(key=lambda item: (-item["score"], item["distance"], item["hospital"]["id"]))
    rejected.sort(key=lambda item: (item["distance"], item["hospital"]["id"]))
    for rank, item in enumerate(eligible, 1):
        item["rank"] = rank

    requirements = {
        "department": normalized_department,
        "requested_bed": normalized_bed,
        "medicine": normalized_medicine,
        "icu_required": icu_required,
        "emergency_required": emergency_required,
        "latitude": origin_latitude,
        "longitude": origin_longitude,
        "location_source": "demo_default" if latitude is None else "request",
    }
    return {
        "status": "ok",
        "source": "database",
        "simulation": True,
        "algorithm": {"version": ALGORITHM_VERSION, "weights": SCORE_WEIGHTS},
        "requirements": requirements,
        "evaluated_count": len(evaluations),
        "count": len(eligible),
        "recommended": eligible[0] if eligible else None,
        "items": eligible,
        "rejected": rejected,
    }
