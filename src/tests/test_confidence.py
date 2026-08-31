import json
import unittest
from pathlib import Path

from src import evaluate_safety_rules, score_with_confidence


def patient(**changes):
    return {
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8, "has_prior_history": True,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    } | changes


class ConfidenceLayerTests(unittest.TestCase):
    def test_certain_deterministic_score_is_never_bare(self):
        result = score_with_confidence(patient(), 2)
        self.assertEqual(result["esi_set"], [2])
        self.assertEqual(result["badge"], "ESI 2 — High confidence")
        self.assertFalse(result["defer_to_senior_nurse"])
        self.assertFalse(result["coverage_guarantee"])

    def test_zero_history_lowers_confidence_and_widens_toward_higher_acuity(self):
        result = score_with_confidence(patient(has_prior_history=False), 3)
        self.assertEqual(result["esi_set"], [2, 3])
        self.assertLess(result["confidence_score"], 0.92)
        self.assertIn("ZERO_HISTORY", result["uncertainty_reasons"])
        self.assertTrue(result["defer_to_senior_nurse"])

    def test_missing_vitals_respect_safety_ceiling_and_never_widen_downward(self):
        result = score_with_confidence(patient(spo2_pct=None), 4)
        self.assertEqual(result["esi_set"], [2, 3])
        self.assertEqual(result["safety_ceiling"], 3)
        self.assertNotIn(4, result["esi_set"])

    def test_low_probability_or_small_gap_returns_contiguous_set(self):
        probabilities = {1: 0.15, 2: 0.36, 3: 0.34, 4: 0.10, 5: 0.05}
        result = score_with_confidence(patient(), 2, class_probabilities=probabilities)
        self.assertEqual(result["esi_set"], [2, 3])
        self.assertEqual(result["top_two_gap"], 0.02)
        self.assertIn("LOW_TOP_CLASS_PROBABILITY", result["uncertainty_reasons"])
        self.assertIn("SMALL_TOP_TWO_GAP", result["uncertainty_reasons"])
        self.assertEqual(result["badge"], "ESI 2-3 — Escalate for senior nurse review")

    def test_full_probability_vector_is_returned(self):
        probabilities = {1: 0.02, 2: 0.86, 3: 0.07, 4: 0.03, 5: 0.02}
        result = score_with_confidence(patient(), 2, class_probabilities=probabilities, probabilities_calibrated=True)
        self.assertEqual(result["class_probabilities"], probabilities)
        self.assertTrue(result["confidence_is_calibrated"])
        self.assertEqual(result["esi_set"], [2])

    def test_missing_data_makes_adjusted_classifier_confidence_uncalibrated(self):
        probabilities = {1: 0.02, 2: 0.86, 3: 0.07, 4: 0.03, 5: 0.02}
        result = score_with_confidence(
            patient(has_prior_history=False), 2,
            class_probabilities=probabilities, probabilities_calibrated=True,
        )
        self.assertFalse(result["confidence_is_calibrated"])
        self.assertGreater(result["evidence_penalty"], 0)
        self.assertEqual(result["top_class_probability"], 0.86)

    def test_probability_input_is_strictly_validated(self):
        invalid = ({1: 1.0}, {1: .1, 2: .2, 3: .3, 4: .4, 5: .1})
        for probabilities in invalid:
            with self.subTest(probabilities=probabilities), self.assertRaises(ValueError):
                score_with_confidence(patient(), 2, class_probabilities=probabilities)

    def test_proposed_score_must_match_probability_top_class(self):
        with self.assertRaises(ValueError):
            score_with_confidence(patient(), 3, class_probabilities={1:.02, 2:.86, 3:.07, 4:.03, 5:.02})

    def test_safety_override_is_applied_before_display(self):
        case = patient(high_risk_presentation=True)
        result = score_with_confidence(case, 4, safety_result=evaluate_safety_rules(case))
        self.assertEqual(result["point_estimate"], 2)
        self.assertEqual(result["esi_set"], [1, 2])
        self.assertIn("SAFETY_RULE_SCORER_DISAGREEMENT", result["uncertainty_reasons"])

    def test_explicit_ordinal_uncertainty_range_is_preserved(self):
        case = patient()
        safety = evaluate_safety_rules(case, (3, 4))
        result = score_with_confidence(case, 4, safety_result=safety)
        self.assertEqual(result["esi_set"], [2, 3])
        self.assertIn("EXPLICIT_UNCERTAINTY_RANGE", result["uncertainty_reasons"])


class DatasetContractTests(unittest.TestCase):
    def test_every_dataset_score_has_confidence_and_badge(self):
        data = json.loads((Path(__file__).parents[2] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        for item in data["patients"]:
            with self.subTest(patient_id=item["patient_id"]):
                result = score_with_confidence(item, int(item["reference_esi"]))
                self.assertTrue(result["esi_set"])
                self.assertIn("confidence_score", result)
                self.assertTrue(result["badge"].startswith("ESI "))
                self.assertEqual(result["esi_set"], list(range(min(result["esi_set"]), max(result["esi_set"]) + 1)))


if __name__ == "__main__":
    unittest.main()
