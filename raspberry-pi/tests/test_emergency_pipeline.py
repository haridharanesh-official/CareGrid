from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import database, hospital_data
from app.services import emergency_case_service


class EmergencyPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_path = hospital_data.DB_PATH
        hospital_data.DB_PATH = Path(self.temp_directory.name) / "caregrid-pipeline-test.db"
        hospital_data.init_hospital_db()
        hospital_data.seed_demo_data()

    def tearDown(self) -> None:
        hospital_data.DB_PATH = self.original_path
        database.configure_database(self.original_path)
        self.temp_directory.cleanup()

    @staticmethod
    def cardiac_payload(**overrides):
        payload = {
            "incident": {"category": "Cardiac", "severity": "CRITICAL"},
            "patient": {"patient_id": "PATIENT-001", "rfid_uid": "D0:DA:F6:5F"},
            "vitals": {"heart_rate": 118, "spo2": 91},
            "requirements": {
                "department": "Cardiology", "bed_type": "Emergency",
                "medicine": "Adrenaline", "equipment": ["Ventilator"],
            },
            "location": {"latitude": 12.9716, "longitude": 77.5946},
        }
        payload.update(overrides)
        return payload

    def test_case_numbers_are_unique_and_null_vitals_are_preserved(self) -> None:
        first = emergency_case_service.create_case(self.cardiac_payload(vitals={}))
        second = emergency_case_service.create_case(self.cardiac_payload(vitals={"heart_rate": None, "spo2": None}))
        self.assertNotEqual(first["case_number"], second["case_number"])
        self.assertTrue(first["case_number"].startswith("CG-EMR-"))
        self.assertIsNone(first["heart_rate"])
        self.assertIsNone(first["spo2"])
        self.assertEqual(first["status"], "CREATED")

    def test_known_and_unknown_rfid_context(self) -> None:
        known = emergency_case_service.create_case(self.cardiac_payload(patient={"rfid_uid": "d0:da:f6:5f"}))
        unknown = emergency_case_service.create_case(self.cardiac_payload(patient={"rfid_uid": "00:11:22:33"}))
        self.assertEqual(known["patient_id"], "PATIENT-001")
        self.assertEqual(known["patient_name"], "Balaji")
        self.assertIsNone(unknown["patient_id"])
        self.assertIsNone(unknown["patient_name"])
        with database.connect() as connection:
            self.assertIsNone(connection.execute("SELECT * FROM patients WHERE patient_id='00:11:22:33'").fetchone())

    def test_recommendation_snapshot_and_rejected_destination(self) -> None:
        case = emergency_case_service.create_case(self.cardiac_payload())
        result = emergency_case_service.recommend_case(case["id"])
        stored = emergency_case_service.get_case(case["id"])
        self.assertGreater(result["count"], 0)
        self.assertEqual(stored["status"], "HOSPITAL_RECOMMENDED")
        self.assertIn("generated_at", stored["recommendation_snapshot"])
        self.assertIn("score_breakdown", result["items"][0])
        rejected = result["rejected"][0]["hospital"]["id"]
        with self.assertRaisesRegex(ValueError, "not eligible"):
            emergency_case_service.confirm_destination(case["id"], rejected)

    def test_full_cardiac_case_prealert_lifecycle_is_idempotent_and_does_not_reserve_resources(self) -> None:
        with database.connect() as connection:
            beds_before = [tuple(row) for row in connection.execute("SELECT hospital_id,bed_type,total,occupied,reserved FROM bed_capacity ORDER BY id")]
            medicine_before = [tuple(row) for row in connection.execute("SELECT hospital_id,medicine_name,total_quantity,reserved_quantity FROM pharmacy_inventory ORDER BY id")]

        case = emergency_case_service.create_case(self.cardiac_payload())
        recommendations = emergency_case_service.recommend_case(case["id"])
        top = recommendations["items"][0]
        confirmed = emergency_case_service.confirm_destination(case["id"], top["hospital"]["id"])
        repeated = emergency_case_service.confirm_destination(case["id"], top["hospital"]["id"])

        self.assertEqual(confirmed["case"]["status"], "PREALERT_SENT")
        self.assertEqual(confirmed["case"]["selected_hospital_id"], top["hospital"]["id"])
        self.assertEqual(confirmed["prealert"]["status"], "SENT")
        self.assertTrue(repeated["idempotent"])
        self.assertEqual(len(emergency_case_service.list_prealerts()), 1)
        self.assertEqual(emergency_case_service.get_prealert(confirmed["prealert"]["id"])["id"], confirmed["prealert"]["id"])

        acknowledged = emergency_case_service.acknowledge_prealert(confirmed["prealert"]["id"], "NURSE-DEMO-001")
        acknowledged_again = emergency_case_service.acknowledge_prealert(confirmed["prealert"]["id"], "NURSE-DEMO-001")
        self.assertEqual(acknowledged["case"]["status"], "ACKNOWLEDGED")
        self.assertTrue(acknowledged_again["idempotent"])
        self.assertEqual(emergency_case_service.mark_arrived(case["id"])["status"], "ARRIVED")
        self.assertEqual(emergency_case_service.close_case(case["id"])["status"], "CLOSED")

        detail = emergency_case_service.get_case(case["id"])
        self.assertEqual(
            [event["event_type"] for event in detail["events"]],
            ["CASE_CREATED", "RECOMMENDATION_GENERATED", "DESTINATION_CONFIRMED", "PREALERT_SENT", "PREALERT_ACKNOWLEDGED", "ARRIVED", "CLOSED"],
        )
        self.assertEqual(detail["prealert"]["payload"]["patient"]["name"], "Balaji")
        self.assertEqual(detail["prealert"]["payload"]["requirements"]["equipment"], ["Ventilator"])

        with database.connect() as connection:
            beds_after = [tuple(row) for row in connection.execute("SELECT hospital_id,bed_type,total,occupied,reserved FROM bed_capacity ORDER BY id")]
            medicine_after = [tuple(row) for row in connection.execute("SELECT hospital_id,medicine_name,total_quantity,reserved_quantity FROM pharmacy_inventory ORDER BY id")]
        self.assertEqual(beds_before, beds_after)
        self.assertEqual(medicine_before, medicine_after)


if __name__ == "__main__":
    unittest.main()
