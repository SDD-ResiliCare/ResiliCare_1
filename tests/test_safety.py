import json
import tempfile
import unittest
from pathlib import Path

from src import (
    apply_safety_ceiling,
    evaluate_safety_rules,
    log_clinician_decision,
    log_provisional_result,
)


def patient(**changes):
    base = {
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8, "immediate_lifesaving_intervention": False,
        "high_risk_presentation": False, "ambiguity_flag": False,
    }
    return base | changes


class SafetyRulesTests(unittest.TestCase):
    def test_all_rules_are_evaluated_and_most_urgent_wins(self):
        result = evaluate_safety_rules(patient(
            immediate_lifesaving_intervention=True,
            high_risk_presentation=True,
            ambiguity_flag=True,
            conflicting_information=["history conflicts with caregiver report"],
        ))
        self.assertEqual(result["provisional_esi"], 1)
        self.assertEqual(len(result["matched_rule_ids"]), 4)
        self.assertIn("IMMEDIATE.LIFE_SAVING_INTERVENTION", result["matched_rule_ids"])
        self.assertIn("REVIEW.CONFLICTING_INFORMATION", result["matched_rule_ids"])

    def test_high_risk_caps_score_at_esi_2(self):
        result = evaluate_safety_rules(patient(high_risk_presentation=True))
        self.assertEqual((result["maximum_allowed_esi"], result["review_priority"]), (2, "HIGH"))
        self.assertTrue(result["requires_clinician_confirmation"])

    def test_review_conditions_cap_at_esi_3_and_highlight(self):
        cases = {
            "REVIEW.AMBIGUOUS_PRESENTATION": {"ambiguity_flag": True},
            "REVIEW.RELEVANT_HISTORY_MISSING": {"relevant_history_missing": True},
            "REVIEW.BORDERLINE_VITALS": {"borderline_vitals": True},
            "REVIEW.WORSENING_VITALS": {"worsening_vitals": True},
            "REVIEW.CONFLICTING_INFORMATION": {"conflicting_information": ["two sources disagree"]},
        }
        for rule_id, inputs in cases.items():
            with self.subTest(rule_id=rule_id):
                result = evaluate_safety_rules(patient(**inputs))
                self.assertEqual(result["provisional_esi"], 3)
                self.assertTrue(result["highlight_alert"])
                self.assertIn(rule_id, result["matched_rule_ids"])

    def test_missing_vitals_are_reported(self):
        result = evaluate_safety_rules(patient(spo2_pct=None, sbp_mmhg=None))
        self.assertEqual(result["provisional_esi"], 3)
        self.assertIn("Missing vitals: spo2_pct, sbp_mmhg", result["missing_or_conflicting_information"])

    def test_zero_history_alone_is_not_an_override(self):
        result = evaluate_safety_rules(patient(has_prior_history=False))
        self.assertEqual(result["status"], "NO_HARD_OVERRIDE")
        self.assertIsNone(result["provisional_esi"])
        self.assertEqual(result["regular_scorer_action"], "RUN")

    def test_supported_uncertainty_ranges_require_review(self):
        for span in ((2, 3), (3, 4)):
            with self.subTest(span=span):
                result = evaluate_safety_rules(patient(), span)
                self.assertEqual(result["provisional_esi"], 3)
                self.assertEqual(result["uncertainty_range"], list(span))

    def test_invalid_uncertainty_range_is_rejected(self):
        with self.assertRaises(ValueError):
            evaluate_safety_rules(patient(), (2, 6))

    def test_safety_ceiling_only_escalates(self):
        cap_two = evaluate_safety_rules(patient(high_risk_presentation=True))
        self.assertEqual(apply_safety_ceiling(4, cap_two), 2)
        self.assertEqual(apply_safety_ceiling(1, cap_two), 1)
        self.assertEqual(apply_safety_ceiling(4, evaluate_safety_rules(patient())), 4)

    def test_provisional_and_clinician_decisions_are_appended(self):
        result = evaluate_safety_rules(patient(ambiguity_flag=True))
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            log_provisional_result(log, "PT-TEST", result)
            log_clinician_decision(log, "PT-TEST", result, "NURSE-7", "override", 3, 2, "Clinical concern")
            events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([event["event_type"] for event in events], ["provisional_safety_result", "clinician_triage_decision"])
        self.assertEqual(events[1]["override_direction"], "escalation")

    def test_override_requires_reason(self):
        result = evaluate_safety_rules(patient(ambiguity_flag=True))
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            log_clinician_decision(Path(directory) / "audit.jsonl", "PT-TEST", result, "NURSE-7", "override", 3, 4)


class DatasetIntegrationTests(unittest.TestCase):
    def test_all_twenty_synthetic_patients_can_be_evaluated(self):
        dataset = json.loads((Path(__file__).parents[1] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        results = {item["patient_id"]: evaluate_safety_rules(item) for item in dataset["patients"]}
        self.assertEqual(len(results), 20)
        self.assertEqual(results["PT-001"]["provisional_esi"], 1)
        self.assertEqual(results["PT-004"]["provisional_esi"], 2)
        self.assertEqual(results["PT-017"]["status"], "NO_HARD_OVERRIDE")
        self.assertTrue(all(result["requires_clinician_confirmation"] for result in results.values()))


if __name__ == "__main__":
    unittest.main()

