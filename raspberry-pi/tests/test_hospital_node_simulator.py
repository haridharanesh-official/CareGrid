from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

from app import database, hospital_data, main
from app.repositories import hospital_repository
from app.services import hospital_node_service, hospital_recommendation_service
from simulator.hospital_node import HospitalNode


class HospitalNodeSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.original_path = hospital_data.DB_PATH
        hospital_data.DB_PATH = Path(self.temp_directory.name) / "caregrid-node-test.db"
        hospital_data.init_hospital_db()
        hospital_data.seed_demo_data()

    def tearDown(self) -> None:
        hospital_data.DB_PATH = self.original_path
        database.configure_database(self.original_path)
        self.temp_directory.cleanup()

    def payload(self, hospital_id: str = "HOSP-002", scenario: str = "NORMAL", sequence: int = 1, timestamp: str | None = None):
        node = HospitalNode(hospital_id, sequence=0)
        node.apply_scenario(scenario)
        return node.resource_payload(sequence=sequence, timestamp=timestamp)

    def recommendation(self, hospital_id: str, **criteria):
        result = hospital_recommendation_service.recommend_hospitals(**criteria)
        return next(item for item in result["items"] + result["rejected"] if item["hospital"]["id"] == hospital_id)

    def set_last_seen(self, hospital_id: str, seconds_ago: int, online: bool = True) -> str:
        timestamp = (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()
        with database.connect() as connection:
            connection.execute(
                "UPDATE hospital_nodes SET last_seen=?,advertised_online=? WHERE hospital_id=?",
                (timestamp, int(online), hospital_id),
            )
        return timestamp

    def test_simulator_resource_payload_validates(self) -> None:
        validated = hospital_node_service.validate_resource_payload(self.payload())
        self.assertEqual(validated["hospital_id"], "HOSP-002")
        self.assertEqual(validated["resources"]["beds"]["EMERGENCY"]["available"], 8)

    def test_invalid_and_unknown_hospital_ids_are_rejected(self) -> None:
        invalid = self.payload()
        invalid["hospital_id"] = "BAD-ID"
        with self.assertRaisesRegex(ValueError, "invalid hospital_id"):
            hospital_node_service.apply_resource_update(invalid)
        unknown = self.payload()
        unknown["hospital_id"] = "HOSP-999"
        with self.assertRaisesRegex(ValueError, "unknown hospital_id"):
            hospital_node_service.apply_resource_update(unknown)

    def test_topic_hospital_id_must_match_payload(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not match"):
            hospital_node_service.apply_resource_update(self.payload(), "HOSP-003")

    def test_mqtt_topic_router_ingests_resource_without_colliding_with_ward(self) -> None:
        class Client:
            def __init__(self) -> None:
                self.published = []

            def publish(self, *args, **kwargs):
                self.published.append((args, kwargs))

        class Message:
            topic = "caregrid/hospital/nodes/HOSP-002/resources"
            payload = json.dumps(self.payload(sequence=7)).encode("utf-8")

        self.assertEqual(main.hospital_node_topic(Message.topic), ("HOSP-002", "resources"))
        self.assertIsNone(main.hospital_node_topic("caregrid/hospital/ward/ward-01/telemetry"))
        main.on_message(Client(), None, Message())
        self.assertEqual(hospital_node_service.get_node("HOSP-002")["resource_version"], 7)

    def test_negative_and_contradictory_resource_values_are_rejected(self) -> None:
        negative = self.payload()
        negative["resources"]["beds"]["EMERGENCY"]["total"] = -1
        with self.assertRaises(ValueError):
            hospital_node_service.validate_resource_payload(negative)
        contradictory = self.payload()
        contradictory["resources"]["pharmacy"]["Adrenaline"]["available_quantity"] = 999
        with self.assertRaisesRegex(ValueError, "contradicts"):
            hospital_node_service.validate_resource_payload(contradictory)
        future = self.payload(timestamp=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        with self.assertRaisesRegex(ValueError, "future"):
            hospital_node_service.validate_resource_payload(future)
        broken_equipment = self.payload()
        broken_equipment["resources"]["equipment"]["Ventilator"].update({"operational": False, "available": 1})
        with self.assertRaisesRegex(ValueError, "not operational"):
            hospital_node_service.validate_resource_payload(broken_equipment)

    def test_node_update_writes_database_tables_and_metadata(self) -> None:
        result = hospital_node_service.apply_resource_update(self.payload(sequence=10))
        self.assertTrue(result["applied"])
        self.assertEqual(result["resource_version"], 10)
        bed = next(item for item in hospital_repository.get_beds("HOSP-002") if item["bed_type"] == "EMERGENCY")
        self.assertEqual(bed["available"], 8)
        self.assertEqual(hospital_node_service.get_node("HOSP-002")["connection_status"], "LIVE")

    def test_node_update_supports_migrated_p03_text_id_schema(self) -> None:
        active_path = hospital_data.DB_PATH
        with tempfile.TemporaryDirectory() as legacy_directory:
            legacy_path = Path(legacy_directory) / "caregrid-legacy.db"
            try:
                hospital_data.DB_PATH = legacy_path
                connection = sqlite3.connect(legacy_path)
                try:
                    connection.executescript(hospital_data.SCHEMA)
                    connection.commit()
                finally:
                    connection.close()
                hospital_data.init_hospital_db()
                hospital_data.seed_demo_data()
                result = hospital_node_service.apply_resource_update(self.payload(sequence=3))
                self.assertTrue(result["applied"])
                self.assertGreater(hospital_repository.get_pharmacy("HOSP-002", "Adrenaline")[0]["available_quantity"], 0)
            finally:
                hospital_data.DB_PATH = active_path
                database.configure_database(active_path)

    def test_node_status_updates_last_seen(self) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        result = hospital_node_service.apply_status_update({
            "hospital_id": "HOSP-002", "online": True, "timestamp": timestamp, "sequence": 2,
        })
        self.assertTrue(result["applied"])
        self.assertEqual(result["node"]["last_seen"], timestamp)

    def test_freshness_live_stale_and_offline_thresholds(self) -> None:
        now = datetime.now(timezone.utc)
        base = {"advertised_online": 1}
        live = hospital_node_service.node_snapshot({**base, "last_seen": (now - timedelta(seconds=15)).isoformat()}, now)
        stale = hospital_node_service.node_snapshot({**base, "last_seen": (now - timedelta(seconds=16)).isoformat()}, now)
        offline = hospital_node_service.node_snapshot({**base, "last_seen": (now - timedelta(seconds=31)).isoformat()}, now)
        self.assertEqual((live["connection_status"], stale["connection_status"], offline["connection_status"]), ("LIVE", "STALE", "OFFLINE"))

    def test_retained_online_timestamp_does_not_keep_node_live_forever(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        result = hospital_node_service.apply_status_update({
            "hospital_id": "HOSP-002", "online": True, "timestamp": old, "sequence": 99,
        })
        self.assertEqual(result["node"]["connection_status"], "OFFLINE")
        self.assertTrue(result["node"]["advertised_online"])

    def test_out_of_order_resource_sequence_is_ignored(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(sequence=105))
        stale = hospital_node_service.apply_resource_update(self.payload(scenario="ICU_FULL", sequence=104))
        self.assertFalse(stale["applied"])
        self.assertEqual(stale["resource_version"], 105)

    def test_newer_resource_sequence_is_applied(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(sequence=105))
        newer = hospital_node_service.apply_resource_update(self.payload(scenario="ICU_FULL", sequence=106))
        self.assertTrue(newer["applied"])
        icu = next(item for item in hospital_repository.get_beds("HOSP-002") if item["bed_type"] == "ICU")
        self.assertEqual(icu["available"], 0)

    def test_cardiology_unavailable_scenario_updates_department(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(scenario="CARDIOLOGY_UNAVAILABLE"))
        cardiology = next(item for item in hospital_repository.get_departments("HOSP-002") if item["name"] == "Cardiology")
        self.assertFalse(cardiology["available"])

    def test_icu_and_emergency_full_scenarios_update_beds(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(scenario="ICU_FULL", sequence=1))
        icu = next(item for item in hospital_repository.get_beds("HOSP-002") if item["bed_type"] == "ICU")
        self.assertEqual(icu["available"], 0)
        hospital_node_service.apply_resource_update(self.payload(scenario="EMERGENCY_BEDS_FULL", sequence=2))
        beds = {item["bed_type"]: item for item in hospital_repository.get_beds("HOSP-002")}
        self.assertEqual(beds["EMERGENCY"]["available"], 0)

    def test_adrenaline_out_scenario_updates_pharmacy(self) -> None:
        hospital_node_service.apply_resource_update(self.payload("HOSP-003", "ADRENALINE_OUT"))
        adrenaline = hospital_repository.get_pharmacy("HOSP-003", "Adrenaline")[0]
        self.assertEqual(adrenaline["available_quantity"], 0)

    def test_ventilator_out_scenario_updates_equipment(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(scenario="VENTILATOR_OUT"))
        ventilator = next(item for item in hospital_repository.get_equipment("HOSP-002") if item["equipment_name"] == "Ventilator")
        self.assertEqual(ventilator["available"], 0)
        self.assertFalse(ventilator["operational"])

    def test_node_offline_and_recovery_scenarios(self) -> None:
        node = HospitalNode("HOSP-002", sequence=0)
        node.apply_scenario("NODE_OFFLINE")
        offline = hospital_node_service.apply_status_update(node.status_payload(sequence=1))
        self.assertEqual(offline["node"]["connection_status"], "OFFLINE")
        node.apply_scenario("RECOVERY")
        recovered = hospital_node_service.apply_resource_update(node.resource_payload(sequence=2))
        self.assertEqual(recovered["node"]["connection_status"], "LIVE")

    def test_cardiology_loss_and_recovery_integration(self) -> None:
        hospital_node_service.apply_resource_update(self.payload("HOSP-002", "NORMAL", 1))
        criteria = dict(
            department="Cardiology", requested_bed="Emergency", emergency_required=True,
            latitude=11.0183, longitude=77.0074,
        )
        initial_result = hospital_recommendation_service.recommend_hospitals(**criteria)
        initial = next(item for item in initial_result["items"] if item["hospital"]["id"] == "HOSP-002")
        self.assertEqual(initial["eligibility"], "eligible")
        self.assertEqual(initial_result["recommended"]["hospital"]["id"], "HOSP-002")
        hospital_node_service.apply_resource_update(self.payload("HOSP-002", "CARDIOLOGY_UNAVAILABLE", 2))
        lost = self.recommendation("HOSP-002", **criteria)
        self.assertEqual(lost["eligibility"], "rejected")
        self.assertIn("NO_REQUIRED_DEPARTMENT", lost["rejection_codes"])
        hospital_node_service.apply_resource_update(self.payload("HOSP-002", "RECOVERY", 3))
        recovered_result = hospital_recommendation_service.recommend_hospitals(**criteria)
        recovered = next(item for item in recovered_result["items"] if item["hospital"]["id"] == "HOSP-002")
        self.assertEqual(recovered["eligibility"], "eligible")
        self.assertEqual(recovered_result["recommended"]["hospital"]["id"], "HOSP-002")

    def test_medicine_outage_integration(self) -> None:
        hospital_node_service.apply_resource_update(self.payload("HOSP-003", "NORMAL", 1))
        available = self.recommendation("HOSP-003", medicine="Adrenaline", emergency_required=True)
        self.assertEqual(available["eligibility"], "eligible")
        hospital_node_service.apply_resource_update(self.payload("HOSP-003", "ADRENALINE_OUT", 2))
        unavailable = self.recommendation("HOSP-003", medicine="Adrenaline", emergency_required=True)
        self.assertEqual(unavailable["eligibility"], "rejected")
        self.assertIn("NO_REQUIRED_MEDICINE", unavailable["rejection_codes"])

    def test_live_stale_offline_recommendation_integration_without_sleep(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(sequence=1))
        live = self.recommendation("HOSP-002", emergency_required=True)
        self.assertEqual(live["resource_source"], "LIVE")
        self.set_last_seen("HOSP-002", 20)
        stale = self.recommendation("HOSP-002", emergency_required=True)
        self.assertEqual(stale["eligibility"], "eligible")
        self.assertIn("HOSPITAL_RESOURCE_NODE_STALE", stale["warning_codes"])
        self.set_last_seen("HOSP-002", 31)
        offline = self.recommendation("HOSP-002", emergency_required=True)
        self.assertEqual(offline["eligibility"], "rejected")
        self.assertIn("HOSPITAL_RESOURCE_NODE_OFFLINE", offline["rejection_codes"])

    def test_stale_node_receives_readiness_penalty(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(sequence=1))
        live_score = self.recommendation("HOSP-002", emergency_required=True)["score"]
        self.set_last_seen("HOSP-002", 20)
        stale_score = self.recommendation("HOSP-002", emergency_required=True)["score"]
        self.assertEqual(stale_score, max(0, live_score - 15))

    def test_hospital_node_api_lists_and_details(self) -> None:
        hospital_node_service.apply_resource_update(self.payload(sequence=1))
        listing = hospital_data.list_hospital_nodes()
        detail = hospital_data.get_hospital_node("hosp-002")
        routes = {route.path for route in hospital_data.hospital_router.routes}
        self.assertEqual(listing["count"], 1)
        self.assertEqual(detail["node"]["hospital_id"], "HOSP-002")
        self.assertIn("beds", detail["resources"])
        self.assertIn("/api/hospital-nodes", routes)
        self.assertIn("/api/hospital-nodes/{hospital_id}", routes)
        with self.assertRaises(HTTPException):
            hospital_data.get_hospital_node("HOSP-404")


if __name__ == "__main__":
    unittest.main()
