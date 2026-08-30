from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from app import database, hospital_data
from app.repositories import hospital_repository


EXPECTED_COUNTS = {
    "hospitals": 5, "departments": 36, "bed_capacity": 25,
    "equipment_inventory": 25, "pharmacy_inventory": 75,
    "hospital_resources": 10, "beds": 0, "patients": 3,
    "doctors": 1, "nurses": 1, "rfid_assignments": 7,
    "emergency_cases": 0, "hospital_prealerts": 0,
    "medicine_reservations": 0, "patient_events": 1,
    "emergency_case_events": 0,
}


class HospitalDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_path = hospital_data.DB_PATH
        hospital_data.DB_PATH = Path(self.temp_directory.name) / "caregrid-test.db"
        hospital_data.init_hospital_db()
        hospital_data.seed_demo_data()

    def tearDown(self) -> None:
        hospital_data.DB_PATH = self.original_path
        database.configure_database(self.original_path)
        self.temp_directory.cleanup()

    def test_database_initializes_requested_schema(self) -> None:
        required = set(EXPECTED_COUNTS)
        connection = sqlite3.connect(hospital_data.DB_PATH)
        try:
            actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            foreign_keys = connection.execute("PRAGMA foreign_key_list(bed_capacity)").fetchall()
        finally:
            connection.close()
        self.assertTrue(required.issubset(actual))
        self.assertTrue(foreign_keys)

    def test_seed_is_idempotent_and_has_exactly_five_unique_hospitals(self) -> None:
        first = hospital_data.seed_demo_data()
        second = hospital_data.seed_demo_data()
        self.assertEqual(first, EXPECTED_COUNTS)
        self.assertEqual(second, EXPECTED_COUNTS)
        response = hospital_data.list_hospitals()
        self.assertEqual(response["count"], 5)
        self.assertEqual(len({item["id"] for item in response["hospitals"]}), 5)

    def test_database_response_metadata_marks_simulation(self) -> None:
        response = hospital_data.list_hospitals()
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["source"], "database")
        self.assertTrue(response["simulation"])
        self.assertTrue(all(item["is_demo"] for item in response["hospitals"]))

    def test_hospital_names_and_capacity_profiles_are_distinct(self) -> None:
        response = hospital_data.list_hospitals()
        self.assertEqual(response["hospitals"][0]["name"], "Ganga Hospital")
        self.assertEqual(hospital_data.get_hospital("HOSP-003")["name"], "KMCH")
        self.assertGreater(len({item["emergency_beds_available"] for item in response["hospitals"]}), 1)

    def test_departments_are_linked_to_hospitals(self) -> None:
        response = hospital_data.get_hospital_departments("HOSP-001")
        self.assertEqual(response["source"], "database")
        self.assertIn("Cardiology", {item["name"] for item in response["departments"]})
        self.assertTrue(all(item["hospital_id"] == "HOSP-001" for item in response["departments"]))

    def test_available_beds_are_computed_and_never_negative(self) -> None:
        response = hospital_data.get_hospital_beds("HOSP-001")
        emergency = next(item for item in response["beds"] if item["bed_type"] == "EMERGENCY")
        self.assertEqual(emergency["available"], emergency["total"] - emergency["occupied"] - emergency["reserved"])
        self.assertTrue(all(item["available"] >= 0 for item in response["beds"]))

    def test_invalid_bed_and_equipment_states_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            database.validate_bed_state(4, 3, 2)
        with self.assertRaises(ValueError):
            database.validate_bed_state(-1, 0, 0)
        with self.assertRaises(ValueError):
            database.validate_equipment_state(2, 2, 1)

    def test_equipment_and_resource_snapshot(self) -> None:
        equipment = hospital_data.get_hospital_equipment("HOSP-001")
        self.assertEqual(equipment["count"], 5)
        self.assertIn("Ventilator", {item["equipment_name"] for item in equipment["equipment"]})
        resources = hospital_data.get_hospital_resources("HOSP-001")
        self.assertEqual(resources["source"], "database")
        self.assertEqual(len(resources["beds"]), 5)
        self.assertTrue(resources["last_updated"])

    def test_pharmacy_availability_is_computed_and_never_negative(self) -> None:
        response = hospital_data.get_hospital_pharmacy("HOSP-001", "")
        self.assertEqual(response["count"], 15)
        self.assertTrue(all(item["available_quantity"] == item["total_quantity"] - item["reserved_quantity"] for item in response["pharmacy"]))
        self.assertTrue(all(item["available_quantity"] >= 0 for item in response["pharmacy"]))
        with self.assertRaises(ValueError):
            database.validate_pharmacy_state(2, 3)

    def test_medicine_search_is_case_insensitive_and_partial(self) -> None:
        adrenaline = hospital_data.search_pharmacy("Adrenaline", None)
        self.assertEqual(adrenaline["count"], 5)
        self.assertEqual(adrenaline["source"], "database")
        self.assertEqual(hospital_data.search_pharmacy("adrenaline", None)["count"], 5)
        self.assertEqual(hospital_data.search_pharmacy("INSU", None)["count"], 5)
        self.assertEqual(hospital_data.search_pharmacy(None, "atro")["count"], 5)

    def test_hospital_404_handling(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            hospital_data.get_hospital("HOSP-404")
        self.assertEqual(raised.exception.status_code, 404)

    def test_requested_routes_are_registered(self) -> None:
        actual = {route.path for route in hospital_data.hospital_router.routes}
        expected = {
            "/api/patients", "/api/patients/{patient_id}", "/api/rfid/{uid}",
            "/api/patients/{patient_id}/events", "/api/hospitals", "/api/hospitals/{hospital_id}",
            "/api/hospitals/{hospital_id}/beds", "/api/hospitals/{hospital_id}/departments",
            "/api/hospitals/{hospital_id}/equipment", "/api/hospitals/{hospital_id}/resources",
            "/api/pharmacy/search", "/api/hospitals/{hospital_id}/pharmacy",
            "/api/hospitals/recommend", "/api/prealerts", "/api/prealerts/{prealert_id}",
            "/api/emergency-cases", "/api/hospitals/{hospital_id}/beds/reserve",
        }
        self.assertTrue(expected.issubset(actual))

    def test_existing_rfid_patient_doctor_and_reserved_lookups(self) -> None:
        balaji = hospital_data.get_rfid_assignment("d0:da:f6:5f")
        doctor = hospital_data.get_rfid_assignment("AA:B4:32:06")
        reserved = hospital_data.get_rfid_assignment("04:06:96:04")
        self.assertEqual(balaji["entity_id"], "PATIENT-001")
        self.assertEqual(balaji["entity"]["name"], "Balaji")
        self.assertEqual(doctor["entity_id"], "DOC-001")
        self.assertTrue(reserved["reserved"])

    def test_compatibility_recommendation_uses_database_resources(self) -> None:
        response = hospital_data.recommend_hospitals(
            department="Cardiology", requested_bed="Emergency", medicine="Adrenaline", emergency_required=True
        )
        self.assertGreater(response["count"], 0)
        self.assertEqual(response["source"], "database")
        for item in response["items"]:
            self.assertGreater(item["availability"]["requested_bed"], 0)
            self.assertGreater(item["availability"]["medicine_quantity"], 0)

    def test_p02_recommendation_is_explainable_and_reports_rejections(self) -> None:
        response = hospital_data.recommend_hospitals(
            department="Cardiology", requested_bed="Emergency", medicine="Adrenaline",
            emergency_required=True, latitude=11.0168, longitude=76.9558,
        )
        self.assertEqual(response["algorithm"]["version"], "p0.2")
        self.assertEqual(response["evaluated_count"], 5)
        self.assertEqual(response["recommended"], response["items"][0])
        self.assertEqual([item["rank"] for item in response["items"]], list(range(1, response["count"] + 1)))
        self.assertTrue(all(response["items"][index - 1]["score"] >= response["items"][index]["score"] for index in range(1, response["count"])))
        self.assertTrue(all(item["score_breakdown"] and not item["rejection_reasons"] for item in response["items"]))
        rejected = next(item for item in response["rejected"] if item["hospital"]["id"] == "HOSP-005")
        self.assertIn("Required department Cardiology is unavailable", rejected["rejection_reasons"])

    def test_p02_hard_filter_rejects_missing_required_medicine(self) -> None:
        response = hospital_data.recommend_hospitals(
            department="Emergency Medicine", requested_bed="Emergency", medicine="Not Stocked",
            emergency_required=True,
        )
        self.assertEqual(response["count"], 0)
        self.assertIsNone(response["recommended"])
        self.assertEqual(len(response["rejected"]), 5)
        self.assertTrue(all(any("Not Stocked" in reason for reason in item["rejection_reasons"]) for item in response["rejected"]))

    def test_p02_requires_complete_gps_pair(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            hospital_data.recommend_hospitals(latitude=11.01)
        self.assertEqual(raised.exception.status_code, 422)

    def test_bed_reservation_and_prealert_workflow_remain_functional(self) -> None:
        before = next(item for item in hospital_repository.get_beds("HOSP-001") if item["bed_type"] == "EMERGENCY")
        reservation = hospital_data.reserve_hospital_bed("HOSP-001", {"bed_type": "Emergency"})
        after = next(item for item in hospital_repository.get_beds("HOSP-001") if item["bed_type"] == "EMERGENCY")
        self.assertEqual(reservation["status"], "reserved")
        self.assertEqual(after["available"], before["available"] - 1)
        emergency = hospital_data.create_emergency_case({
            "name": "Balaji", "hospitalId": "HOSP-001", "category": "Cardiac",
            "severity": "Critical", "department": "Cardiology", "bedType": "Emergency",
            "heartRate": 78, "spo2": 98, "eta": 8,
        })
        alert = hospital_data.create_prealert({
            "caseId": emergency["id"], "hospitalId": "HOSP-001", "patient": "Balaji",
            "category": "Cardiac", "severity": "Critical", "bedType": "Emergency",
            "medicine": "Adrenaline", "vitals": {"heartRate": 78, "spo2": 98},
        })
        self.assertEqual(alert["deliveryStatus"], "Delivered")
        self.assertEqual(hospital_data.list_prealerts(50)["count"], 1)


if __name__ == "__main__":
    unittest.main()
