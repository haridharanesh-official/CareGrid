from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from app import main


class RealtimeStateTests(unittest.TestCase):
    def setUp(self) -> None:
        with main.state_lock:
            main.device_state.clear()

    def test_freshness_thresholds_use_last_telemetry(self) -> None:
        now = datetime.now(timezone.utc)
        base = {"device_id": "hospital_ward_01", "node_type": "smart_hospital_ward", "data": {}}
        live = main.node_freshness({**base, "last_seen": (now - timedelta(seconds=10)).isoformat()}, now)
        stale = main.node_freshness({**base, "last_seen": (now - timedelta(seconds=20)).isoformat()}, now)
        offline = main.node_freshness({**base, "last_seen": (now - timedelta(seconds=31)).isoformat()}, now)
        self.assertEqual((live["connection_status"], stale["connection_status"], offline["connection_status"]), ("LIVE", "STALE", "OFFLINE"))
        self.assertTrue(live["online"])
        self.assertFalse(stale["online"])

    def test_status_panic_and_rfid_do_not_refresh_last_seen(self) -> None:
        last_seen = (datetime.now(timezone.utc) - timedelta(seconds=45)).isoformat()
        main.device_state["hospital_ward_01"] = {
            "device_id": "hospital_ward_01", "node_type": "smart_hospital_ward",
            "last_seen": last_seen, "data": {},
        }
        main.update_online_state("hospital_ward_01", True)
        main.update_panic_state("hospital_ward_01", True)
        main.update_rfid_state("hospital_ward_01", "D0:DA:F6:5F")
        state = main.device_state["hospital_ward_01"]
        self.assertEqual(state["last_seen"], last_seen)
        self.assertTrue(state["data"]["emergency"]["panic"])
        self.assertEqual(state["data"]["rfid"]["last_uid"], "D0:DA:F6:5F")
        self.assertEqual(main.node_freshness(state)["connection_status"], "OFFLINE")

    def test_canonical_and_legacy_telemetry_are_accepted(self) -> None:
        canonical = main.normalize_telemetry({"device_id": "hospital_ward_01", "node_type": "smart_hospital_ward", "data": {"vitals": {"valid": False}}})
        legacy = main.normalize_telemetry({"device_id": "hospital_ward_01", "node_type": "smart_hospital_ward", "vitals": {"valid": False}})
        self.assertIn("vitals", canonical.data)
        self.assertIn("vitals", legacy.data)


if __name__ == "__main__":
    unittest.main()
