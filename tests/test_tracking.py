"""Verify gaps and recovery across receiver changes and restarts."""

import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).parents[1] / "custom_components/bm2_history/tracking.py"
spec = importlib.util.spec_from_file_location("bm2_tracking", path)
tracking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tracking)


class TrackingTests(unittest.TestCase):
    def decision(self, state, freshest, now):
        return tracking.should_recover(state, freshest, now, 180, 3600)

    def test_initial_sync(self):
        self.assertTrue(self.decision({}, 10000, 10001))

    def test_receiver_handoff_without_gap(self):
        state = {"last_seen": 10000, "last_sync": 9900}
        self.assertFalse(self.decision(state, max(10000, 10030), 10031))
        self.assertFalse(state.get("pending", False))

    def test_stale_value_does_not_count_as_reachable(self):
        state = {"last_seen": 10000, "last_sync": 9900}
        self.assertFalse(self.decision(state, 10000, 10200))
        self.assertTrue(state["pending"])

    def test_return_from_gap_requests_recovery(self):
        state = {"last_seen": 10000, "last_sync": 9900}
        self.assertTrue(self.decision(state, 10200, 10201))
        self.assertTrue(state["pending"])

    def test_pending_survives_restart_and_fresh_reports(self):
        state = {"last_seen": 10200, "last_sync": 9900, "pending": True}
        self.assertTrue(self.decision(state, 10230, 10231))

    def test_unavailable_sources_wait_for_return(self):
        state = {"last_seen": 10000, "pending": True}
        self.assertFalse(self.decision(state, 0, 10200))

    def test_hourly_sync(self):
        state = {"last_seen": 14000, "last_sync": 10000}
        self.assertTrue(self.decision(state, 14030, 14031))


if __name__ == "__main__":
    unittest.main()
