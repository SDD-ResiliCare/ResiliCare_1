import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from resilicare import confirmation_status, pending_confirmation, record_clinician_confirmation


class ConfirmationTests(unittest.TestCase):
    def test_pending_confirmation_times_out_to_senior_review_without_changing_esi(self):
        now = datetime(2026, 9, 1, tzinfo=timezone.utc)
        pending = pending_confirmation(encounter_id="Q-001", now=now)
        status = confirmation_status(pending, now=now + timedelta(minutes=16))
        self.assertEqual(status["status"], "TIMED_OUT_SENIOR_REVIEW")
        self.assertFalse(status["routing_allowed"])
        self.assertEqual(status["review_action"], "SENIOR_REVIEW_REQUIRED")

    def test_confirmation_captures_displayed_rules_and_role(self):
        with tempfile.TemporaryDirectory() as directory:
            event = record_clinician_confirmation(
                Path(directory) / "audit.jsonl", patient_id="Q-001", encounter_id="Q-001",
                clinician_id="NURSE-1", clinician_role="rn",
                ai_result={"point_estimate": 3, "matched_safety_rules": ["A", "B"], "explanation_rule_ids": ["A", "B", "C"]},
            )
        self.assertEqual(event["clinician_role"], "RN")
        self.assertEqual(event["displayed_safety_rules"], ["A", "B"])


if __name__ == "__main__":
    unittest.main()
