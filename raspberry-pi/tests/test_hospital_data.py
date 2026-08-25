from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app import hospital_data


EXPECTED_COUNTS = {
    "hospitals": 5,
    "departments": 26,
    "beds": 294,
    "pharmacy_inventory": 75,
    "patients": 3,
    "doctors": 1,
    "nurses": 1,
    "rfid_assignments": 7,
    "emergency_cases": 0,
    "hospital_prealerts": 0,
    "medicine_reservations": 0,
    "patient_events": 1,
}


class HospitalDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_path = hospital_data.DB_PATH
        hospital_data.DB_PATH = Path(self.temp_directory.name) / "caregrid-test.db"
        hospital_data.init_hospital_db()

    def tearDown(self) -> None:
        hospital_data.DB_PATH = self.original_path
        self.temp_directory.cleanup()

    def test_schema_contains_every_requested_domain_table(self) -> None:
        required = set(EXPECTED_COUNTS)
        connection = sqlite3.connect(hospital_data.DB_PATH)
        try:
            actual = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        finally:
            connection.close()
        self.assertTrue(required.issubset(actual))

    def test_seed_is_idempotent(self) -> None:
        first = hospital_data.seed_demo_data()
        second = hospital_data.seed_demo_data()
        self.assertEqual(first, EXPECTED_COUNTS)
        self.assertEqual(second, EXPECTED_COUNTS)

    def test_rfid_patient_doctor_reserved_and_unknown_lookups(self) -> None:
        hospital_data.seed_demo_data()
        balaji = hospital_data.get_rfid_assignment("d0:da:f6:5f")
        doctor = hospital_data.get_rfid_assignment("AA:B4:32:06")
        reserved = hospital_data.get_rfid_assignment("04:06:96:04")
        self.assertEqual(balaji["entity_id"], "PATIENT-001")
        self.assertEqual(balaji["entity"]["name"], "Balaji")
        self.assertEqual(doctor["entity_id"], "DOC-001")
        self.assertEqual(doctor["entity"]["department"], "Emergency Medicine")
        self.assertFalse(reserved["known"])
        self.assertTrue(reserved["reserved"])
        with self.assertRaisesRegex(Exception, "404"):
            hospital_data.get_rfid_assignment("00:00:00:00")

    def test_hospital_listing_has_five_distinct_capacity_profiles(self) -> None:
        hospital_data.seed_demo_data()
        response = hospital_data.list_hospitals()
        self.assertEqual(response["count"], 5)
        self.assertEqual(len({item["name"] for item in response["items"]}), 5)
        self.assertGreater(len({item["emergency_beds_available"] for item in response["items"]}), 1)
        trauma = hospital_data.get_hospital("HOSP-003")
        self.assertEqual(trauma["name"], "CareGrid Emergency & Trauma Centre")

    def test_pharmacy_search_returns_each_hospital_and_varied_stock(self) -> None:
        hospital_data.seed_demo_data()
        response = hospital_data.search_pharmacy("Adrenaline")
        self.assertEqual(response["count"], 5)
        self.assertEqual(len({item["hospital_id"] for item in response["items"]}), 5)
        self.assertGreater(len({item["quantity"] for item in response["items"]}), 1)
        central = hospital_data.get_hospital_pharmacy("HOSP-001", "Adrenaline")
        self.assertEqual(central["count"], 1)
        self.assertEqual(central["items"][0]["medicine"], "Adrenaline")

    def test_requested_routes_are_registered(self) -> None:
        actual = {route.path for route in hospital_data.hospital_router.routes}
        expected = {
            "/api/patients", "/api/patients/{patient_id}", "/api/rfid/{uid}",
            "/api/patients/{patient_id}/events", "/api/hospitals", "/api/hospitals/{hospital_id}",
            "/api/hospitals/{hospital_id}/beds", "/api/hospitals/{hospital_id}/departments",
            "/api/pharmacy/search", "/api/hospitals/{hospital_id}/pharmacy",
            "/api/hospitals/recommend", "/api/prealerts", "/api/prealerts/{prealert_id}",
            "/api/emergency-cases", "/api/hospitals/{hospital_id}/beds/reserve",
        }
        self.assertTrue(expected.issubset(actual))

    def test_hospital_recommendation_enforces_requirements(self) -> None:
        hospital_data.seed_demo_data()
        response = hospital_data.recommend_hospitals(
            department="Cardiology",
            requested_bed="Emergency",
            medicine="Adrenaline",
            emergency_required=True,
        )
        self.assertGreater(response["count"], 0)
        self.assertEqual([item["rank"] for item in response["items"]], list(range(1, response["count"] + 1)))
        for item in response["items"]:
            self.assertEqual(item["eligibility"], "eligible")
            self.assertGreater(item["availability"]["requested_bed"], 0)
            self.assertGreater(item["availability"]["medicine_quantity"], 0)

    def test_emergency_case_and_prealert_workflow(self) -> None:
        hospital_data.seed_demo_data()
        reservation = hospital_data.reserve_hospital_bed("HOSP-001", {"bed_type": "Emergency"})
        self.assertEqual(reservation["status"], "reserved")
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
