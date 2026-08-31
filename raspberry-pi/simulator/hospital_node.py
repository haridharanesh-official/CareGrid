from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any


HOSPITALS = {
    "HOSP-002": "PSG Hospitals",
    "HOSP-003": "KMCH",
    "HOSP-004": "Sri Ramakrishna Hospital",
    "HOSP-005": "Government Medical College Hospital",
}

SCENARIOS = (
    "NORMAL", "HIGH_LOAD", "ICU_FULL", "EMERGENCY_BEDS_FULL", "ADRENALINE_LOW",
    "ADRENALINE_OUT", "VENTILATOR_OUT", "CARDIOLOGY_UNAVAILABLE", "NODE_OFFLINE", "RECOVERY",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _beds(total: int, occupied: int, reserved: int) -> dict[str, int]:
    return {"total": total, "occupied": occupied, "reserved": reserved, "available": total - occupied - reserved}


def _medicine(total: int, reserved: int) -> dict[str, int]:
    return {"total_quantity": total, "reserved_quantity": reserved, "available_quantity": total - reserved}


BASELINES: dict[str, dict[str, Any]] = {
    "HOSP-002": {
        "beds": {"EMERGENCY": _beds(10, 1, 1), "ICU": _beds(10, 2, 1), "GENERAL": _beds(72, 46, 4)},
        "departments": {"Emergency Medicine": {"available": True, "doctors_on_duty": 4}, "Cardiology": {"available": True, "doctors_on_duty": 3}},
        "equipment": {"Ventilator": {"total": 10, "available": 6, "reserved": 1, "operational": True}, "Oxygen Supply": {"total": 24, "available": 18, "reserved": 2, "operational": True}},
        "pharmacy": {"Adrenaline": _medicine(30, 5)},
    },
    "HOSP-003": {
        "beds": {"EMERGENCY": _beds(16, 6, 2), "ICU": _beds(14, 5, 2), "GENERAL": _beds(80, 51, 6)},
        "departments": {"Emergency Medicine": {"available": True, "doctors_on_duty": 5}, "Cardiology": {"available": True, "doctors_on_duty": 4}},
        "equipment": {"Ventilator": {"total": 14, "available": 9, "reserved": 1, "operational": True}, "Oxygen Supply": {"total": 30, "available": 25, "reserved": 2, "operational": True}},
        "pharmacy": {"Adrenaline": _medicine(36, 4)},
    },
    "HOSP-004": {
        "beds": {"EMERGENCY": _beds(8, 5, 1), "ICU": _beds(6, 3, 1), "GENERAL": _beds(48, 30, 4)},
        "departments": {"Emergency Medicine": {"available": True, "doctors_on_duty": 3}, "Cardiology": {"available": True, "doctors_on_duty": 2}},
        "equipment": {"Ventilator": {"total": 6, "available": 3, "reserved": 1, "operational": True}, "Oxygen Supply": {"total": 16, "available": 11, "reserved": 2, "operational": True}},
        "pharmacy": {"Adrenaline": _medicine(18, 3)},
    },
    "HOSP-005": {
        "beds": {"EMERGENCY": _beds(14, 9, 2), "ICU": _beds(6, 4, 1), "GENERAL": _beds(96, 68, 8)},
        "departments": {"Emergency Medicine": {"available": True, "doctors_on_duty": 4}, "Cardiology": {"available": False, "doctors_on_duty": 0}},
        "equipment": {"Ventilator": {"total": 9, "available": 5, "reserved": 2, "operational": True}, "Oxygen Supply": {"total": 28, "available": 20, "reserved": 3, "operational": True}},
        "pharmacy": {"Adrenaline": _medicine(22, 4)},
    },
}


class HospitalNode:
    def __init__(self, hospital_id: str, sequence: int | None = None) -> None:
        normalized = hospital_id.strip().upper()
        if normalized not in HOSPITALS:
            raise ValueError(f"Unsupported simulated hospital: {hospital_id}")
        self.hospital_id = normalized
        self.hospital_name = HOSPITALS[normalized]
        self.sequence = sequence if sequence is not None else int(time.time() * 1000)
        self.scenario = "NORMAL"
        self.online = True
        self.resources = copy.deepcopy(BASELINES[normalized])

    @property
    def resource_topic(self) -> str:
        return f"caregrid/hospital/nodes/{self.hospital_id}/resources"

    @property
    def status_topic(self) -> str:
        return f"caregrid/hospital/nodes/{self.hospital_id}/status"

    def next_sequence(self) -> int:
        self.sequence += 1
        return self.sequence

    def apply_scenario(self, scenario: str) -> None:
        selected = scenario.strip().upper()
        if selected not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {scenario}")
        self.scenario = selected
        self.online = selected != "NODE_OFFLINE"
        self.resources = copy.deepcopy(BASELINES[self.hospital_id])
        if selected in {"NORMAL", "RECOVERY", "NODE_OFFLINE"}:
            return
        if selected == "HIGH_LOAD":
            for bed in self.resources["beds"].values():
                bed.update(_beds(bed["total"], max(0, bed["total"] - 2), 1))
        elif selected == "ICU_FULL":
            total = self.resources["beds"]["ICU"]["total"]
            self.resources["beds"]["ICU"] = _beds(total, total, 0)
        elif selected == "EMERGENCY_BEDS_FULL":
            total = self.resources["beds"]["EMERGENCY"]["total"]
            self.resources["beds"]["EMERGENCY"] = _beds(total, total, 0)
        elif selected == "ADRENALINE_LOW":
            self.resources["pharmacy"]["Adrenaline"] = _medicine(10, 8)
        elif selected == "ADRENALINE_OUT":
            self.resources["pharmacy"]["Adrenaline"] = _medicine(30, 30)
        elif selected == "VENTILATOR_OUT":
            ventilator = self.resources["equipment"]["Ventilator"]
            ventilator.update({"available": 0, "reserved": 0, "operational": False})
        elif selected == "CARDIOLOGY_UNAVAILABLE":
            self.resources["departments"]["Cardiology"] = {"available": False, "doctors_on_duty": 0}

    def resource_payload(self, timestamp: str | None = None, sequence: int | None = None) -> dict[str, Any]:
        version = self.next_sequence() if sequence is None else sequence
        published_at = timestamp or utc_now()
        return {
            "hospital_id": self.hospital_id,
            "hospital_name": self.hospital_name,
            "node_type": "simulated_hospital",
            "online": self.online,
            "sequence": version,
            "resource_version": version,
            "timestamp": published_at,
            "updated_at": published_at,
            "emergency_capability": True,
            "icu_capability": True,
            "scenario": self.scenario,
            "resources": copy.deepcopy(self.resources),
        }

    def status_payload(self, online: bool | None = None, timestamp: str | None = None, sequence: int | None = None) -> dict[str, Any]:
        return {
            "hospital_id": self.hospital_id,
            "online": self.online if online is None else online,
            "timestamp": timestamp or utc_now(),
            "sequence": self.next_sequence() if sequence is None else sequence,
        }
