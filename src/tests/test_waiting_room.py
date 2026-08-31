import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import (
    complete_reassessment,
    create_waiting_entry,
    detect_vital_deterioration,
    load_waiting_room_config,
    tick_waiting_room,
)

START = datetime(2026, 9, 1, 8, 0, tzinfo=timezone.utc)


def patient(patient_id, age=30, **changes):
    return {
        "patient_id": patient_id, "age_years": age, "has_prior_history": True,
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    } | changes


class WaitingRoomTests(unittest.TestCase):
    def test_config_does_not_mislabel_demo_intervals_as_esi_standard(self):
        config = load_waiting_room_config()
        self.assertIn("NOT_AN_ESI_TIME_STANDARD", config["policy_type"])
        self.assertEqual(config["reassessment_ceiling_minutes"]["1"], 0)

    def test_overdue_patient_is_flagged_without_automatic_esi_change(self):
        entry = create_waiting_entry(patient("PT-A"), 4, START)
        result = tick_waiting_room([entry], START + timedelta(minutes=61))[0]
        self.assertTrue(result["reassessment_required"])
        self.assertEqual((result["current_esi"], result["reassessment_count"]), (4, 1))
        self.assertEqual(result["status"], "REASSESSMENT_REQUIRED")

    def test_active_time_alert_is_not_logged_repeatedly(self):
        entry = create_waiting_entry(patient("PT-A"), 4, START)
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            queue = tick_waiting_room([entry], START + timedelta(minutes=61), log_path=log)
            tick_waiting_room(queue, START + timedelta(minutes=62), log_path=log)
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "waiting_room_retriage")
        self.assertEqual(events[0]["trigger_reasons"], ["REASSESSMENT_INTERVAL_EXCEEDED"])
        self.assertIn("new_queue_rank", events[0])

    def test_worsening_age_adjusted_vitals_escalate_to_review_and_move_queue(self):
        stable = create_waiting_entry(patient("PT-STABLE"), 3, START)
        worsening = create_waiting_entry(patient("PT-WORSE"), 4, START)
        queue = tick_waiting_room(
            [stable, worsening], START + timedelta(minutes=5),
            vital_updates={"PT-WORSE": {"hr_bpm": 125, "spo2_pct": 92}},
        )
        moved = next(item for item in queue if item["patient_id"] == "PT-WORSE")
        self.assertEqual((moved["current_esi"], moved["queue_rank"]), (3, 1))
        self.assertIn("REVIEW.WORSENING_VITALS", moved["latest_confidence"]["matched_safety_rules"])

    def test_rescorer_can_escalate_but_never_downgrade(self):
        entry = create_waiting_entry(patient("PT-A"), 3, START)
        escalated = tick_waiting_room([entry], START + timedelta(minutes=31), rescorer=lambda _p, _e: 2)[0]
        self.assertEqual(escalated["current_esi"], 2)
        fresh = create_waiting_entry(patient("PT-B"), 3, START)
        not_downgraded = tick_waiting_room([fresh], START + timedelta(minutes=31), rescorer=lambda _p, _e: 5)[0]
        self.assertEqual(not_downgraded["current_esi"], 3)

    def test_non_worsening_reentered_vitals_reset_assessment_timer(self):
        entry = create_waiting_entry(patient("PT-A"), 3, START)
        queue = tick_waiting_room([entry], START + timedelta(minutes=20), vital_updates={"PT-A": {"hr_bpm": 82}})
        self.assertFalse(queue[0]["reassessment_required"])
        self.assertEqual(queue[0]["last_assessed_at"], (START + timedelta(minutes=20)).isoformat())

    def test_only_vitals_can_enter_the_waiting_room_update_channel(self):
        entry = create_waiting_entry(patient("PT-A"), 3, START)
        with self.assertRaises(ValueError):
            tick_waiting_room([entry], START + timedelta(minutes=1), vital_updates={"PT-A": {"audio_signal": 0.9}})

    def test_esi_one_is_immediately_flagged(self):
        entry = create_waiting_entry(patient("PT-A"), 1, START)
        result = tick_waiting_room([entry], START)[0]
        self.assertTrue(result["reassessment_required"])
        self.assertEqual(result["queue_rank"], 1)

    def test_deterioration_uses_normalized_distance(self):
        changes = detect_vital_deterioration(patient("PT-A"), patient("PT-A", hr_bpm=125))
        self.assertEqual(changes[0]["vital"], "hr_bpm")
        self.assertGreater(changes[0]["normalized_change"], 0)

    def test_timezone_is_required(self):
        with self.assertRaises(ValueError):
            create_waiting_entry(patient("PT-A"), 3, datetime(2026, 9, 1, 8, 0))

    def test_duplicate_patients_and_unknown_updates_are_rejected(self):
        entry = create_waiting_entry(patient("PT-A"), 3, START)
        with self.assertRaises(ValueError):
            tick_waiting_room([entry, entry], START)
        with self.assertRaises(ValueError):
            tick_waiting_room([entry], START, vital_updates={"PT-UNKNOWN": {"hr_bpm": 90}})

    def test_clinician_completion_resets_timer_and_is_logged(self):
        entry = create_waiting_entry(patient("PT-A"), 3, START)
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            alerted = tick_waiting_room([entry], START + timedelta(minutes=31), log_path=log)[0]
            completed = complete_reassessment(alerted, START + timedelta(minutes=32), "NURSE-7", log_path=log)
            still_waiting = tick_waiting_room([completed], START + timedelta(minutes=50), log_path=log)[0]
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertFalse(still_waiting["reassessment_required"])
        self.assertEqual(still_waiting["last_reassessed_by"], "NURSE-7")
        self.assertEqual([event["event_type"] for event in events], [
            "waiting_room_retriage", "waiting_room_reassessment_completed",
        ])


class DatasetWaitingRoomTests(unittest.TestCase):
    def test_all_twenty_synthetic_patients_can_enter_and_be_ranked(self):
        data = json.loads((Path(__file__).parents[2] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        entries = [create_waiting_entry(item, int(item["reference_esi"]), START) for item in data["patients"]]
        queue = tick_waiting_room(entries, START + timedelta(minutes=1))
        self.assertEqual(len(queue), 20)
        self.assertEqual([item["queue_rank"] for item in queue], list(range(1, 21)))
        self.assertTrue(all(item["reassessment_required"] for item in queue if item["current_esi"] == 1))


if __name__ == "__main__":
    unittest.main()
