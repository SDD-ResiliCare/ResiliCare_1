import json
import unittest
from pathlib import Path

from resilicare import score_with_confidence


def patient(**changes):
    return {
        "patient_id": "PT-TEST", "age_years": 30, "has_prior_history": True,
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    } | changes


class ScoreExplanationTests(unittest.TestCase):
    def test_age_adjusted_vital_explanation_contains_value_and_exact_floor(self):
        case = patient(age_years=7, hr_bpm=100, rr_bpm=20, spo2_pct=91, sbp_mmhg=100, temp_c=37)
        result = score_with_confidence(case, 3)
        self.assertIn("SpO₂ 91%", result["explanation_text"])
        self.assertIn("age-adjusted reference floor of 94%", result["explanation_text"])
        self.assertIn("REVIEW.BORDERLINE_VITALS", result["explanation_rule_ids"])

    def test_immediate_rule_is_explained_first(self):
        result = score_with_confidence(patient(immediate_lifesaving_intervention=True), 4)
        self.assertEqual(result["explanation_rule_ids"][0], "IMMEDIATE.LIFE_SAVING_INTERVENTION")
        self.assertTrue(result["explanation_lines"][0].startswith("ESI 1 —"))

    def test_explanation_is_never_more_than_two_lines(self):
        result = score_with_confidence(patient(
            immediate_lifesaving_intervention=True, high_risk_presentation=True,
            ambiguity_flag=True, spo2_pct=None, has_prior_history=False,
        ), 4)
        self.assertEqual(len(result["explanation_lines"]), 2)

    def test_missing_vital_and_zero_history_are_visible(self):
        missing = score_with_confidence(patient(spo2_pct=None), 4)
        no_history = score_with_confidence(patient(has_prior_history=False), 4)
        self.assertIn("required observed vitals are missing: SpO₂", missing["explanation_text"])
        self.assertIn("no prior history is on file", no_history["explanation_text"])

    def test_clear_case_still_has_verifiable_fallback(self):
        result = score_with_confidence(patient(), 4)
        self.assertEqual(result["explanation_rule_ids"], ["NO_HARD_SAFETY_OVERRIDE"])
        self.assertIn("upstream scorer", result["explanation_text"])


class DatasetExplanationContractTests(unittest.TestCase):
    def test_every_synthetic_score_has_one_or_two_explanation_lines(self):
        data = json.loads((Path(__file__).parents[1] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        for item in data["patients"]:
            with self.subTest(patient_id=item["patient_id"]):
                result = score_with_confidence(item, int(item["reference_esi"]))
                self.assertIn(len(result["explanation_lines"]), {1, 2})
                self.assertTrue(all(line.startswith("ESI ") for line in result["explanation_lines"]))


if __name__ == "__main__":
    unittest.main()
