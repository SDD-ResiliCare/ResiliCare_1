import json
import unittest
from pathlib import Path

from src import COMBAT_MODE_QUEUE_THRESHOLD, replay_arrivals

PATIENTS = json.loads((Path(__file__).parents[2] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))["patients"]


class SurgeSimulationTests(unittest.TestCase):
    def test_same_window_replays_exactly_three_times_baseline_arrivals(self):
        quiet = replay_arrivals(PATIENTS, multiplier=1)
        surge = replay_arrivals(PATIENTS, multiplier=3)
        self.assertEqual(surge["arrival_count"], quiet["arrival_count"] * 3)
        self.assertEqual(surge["arrival_window_minutes"], quiet["arrival_window_minutes"])
        self.assertEqual((quiet["queue_length"], surge["queue_length"]), (7, 21))

    def test_only_three_x_load_crosses_confirmed_combat_threshold(self):
        quiet = replay_arrivals(PATIENTS, multiplier=1)
        surge = replay_arrivals(PATIENTS, multiplier=3)
        self.assertEqual(COMBAT_MODE_QUEUE_THRESHOLD, 20)
        self.assertFalse(quiet["automatic_combat_mode"])
        self.assertTrue(surge["automatic_combat_mode"])

    def test_replayed_encounters_have_unique_queue_ids(self):
        queue = replay_arrivals(PATIENTS, multiplier=3)["queue"]
        self.assertEqual(len({item["patient_id"] for item in queue}), 21)
        self.assertTrue(all(item["patient"]["source_patient_id"].startswith("PT-") for item in queue))

    def test_deteriorating_low_acuity_encounter_moves_forward(self):
        result = replay_arrivals(PATIENTS, multiplier=3, deteriorate_first_patient=True)
        self.assertTrue(result["deterioration_demo"]["moved_forward"])


if __name__ == "__main__":
    unittest.main()
