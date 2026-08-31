import tempfile
import unittest
from pathlib import Path

from src import combat_mode_state, critical_safety_badge, read_audit_events, record_combat_acknowledgement


class CombatModeTests(unittest.TestCase):
    def test_queue_threshold_and_manual_trigger_are_explicit(self):
        self.assertFalse(combat_mode_state(19)["active"])
        self.assertEqual(combat_mode_state(20)["trigger"], "QUEUE_LENGTH")
        self.assertEqual(combat_mode_state(7, manually_declared=True)["trigger"], "MANUAL")
        self.assertFalse(combat_mode_state(20)["scoring_changed"])

    def test_exactly_one_prioritized_safety_badge_is_returned(self):
        badge = critical_safety_badge({
            "matched_safety_rules": ["IMMEDIATE.X", "HIGH_RISK.Y"],
            "explanation_lines": ["Immediate intervention is flagged."],
        })
        self.assertEqual(badge, {"level": "IMMEDIATE", "label": "Immediate action", "reason": "Immediate intervention is flagged."})

    def test_acknowledgement_appends_required_snapshot(self):
        ai = {"point_estimate": 2, "display_score": "2", "esi_set": [2], "confidence_score": 0.91, "confidence_label": "High", "badge": "ESI 2 — High confidence"}
        surge = combat_mode_state(21)
        badge = critical_safety_badge(ai)
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            event = record_combat_acknowledgement(log, patient_id="Q-001", clinician_id="NURSE-7", clinician_role="RN", ai_result=ai, surge_state=surge, safety_badge=badge)
            self.assertEqual(read_audit_events(log), [event])
        self.assertEqual(event["event_type"], "combat_mode_acknowledgement")
        self.assertEqual(event["current_ai"]["confidence_score"], 0.91)
        self.assertEqual(event["surge_state"]["queue_length"], 21)

    def test_acknowledgement_is_rejected_outside_combat_mode(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            record_combat_acknowledgement(
                Path(directory) / "audit.jsonl", patient_id="Q-001", clinician_id="NURSE-7", clinician_role="RN",
                ai_result={"point_estimate": 3, "confidence_score": 0.8},
                surge_state=combat_mode_state(7), safety_badge={"level": "STANDARD", "label": "None", "reason": "None"},
            )


if __name__ == "__main__":
    unittest.main()
