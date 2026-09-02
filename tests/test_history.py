import json
import unittest
from pathlib import Path
from typing import Any

from src import prepare_history_context, score_with_confidence, weighted_risk_signal


def patient(has_prior_history: Any = True, **changes):
    return {
        "has_prior_history": has_prior_history,
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    } | changes


class MissingHistoryTests(unittest.TestCase):
    def test_zero_history_features_are_forced_to_zero_without_mutating_input(self):
        original = patient(False, history_features={"comorbidity_burden": 0.9, "medication_risk": 0.7})
        context = prepare_history_context(original)
        self.assertEqual(context["history_features"], {"comorbidity_burden": 0.0, "medication_risk": 0.0})
        self.assertEqual(original["history_features"]["comorbidity_burden"], 0.9)
        self.assertFalse(context["history_imputation_applied"])

    def test_zero_history_reweights_history_vital_blend_entirely_to_vitals(self):
        context = prepare_history_context(patient(False))
        self.assertEqual(context["scorer_weights"], {"observed_vitals": 1.0, "prior_history": 0.0})
        self.assertEqual(weighted_risk_signal(0.8, None, context), 0.8)

    def test_available_history_is_preserved_and_blended(self):
        context = prepare_history_context(patient(True), {"comorbidity_burden": 0.6})
        self.assertEqual(context["history_features"], {"comorbidity_burden": 0.6})
        self.assertEqual(context["history_missingness_indicator"], 0)
        self.assertEqual(weighted_risk_signal(0.8, 0.4, context), 0.7)

    def test_history_flag_must_be_an_explicit_boolean(self):
        for value in (None, 0, 1, "false", "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_history_context(patient(value))

    def test_zero_history_notice_is_in_confidence_output(self):
        result = score_with_confidence(patient(False), 3)
        notice = "No prior history on file — score based on presenting vitals only."
        self.assertEqual(result["history_context"]["score_basis"], "PRESENTING_VITALS_ONLY")
        self.assertEqual(result["ui_notices"], [notice])

    def test_invalid_blend_weights_are_rejected(self):
        context = prepare_history_context(patient(False))
        context["scorer_weights"] = {"observed_vitals": 0.8, "prior_history": 0.1}
        with self.assertRaises(ValueError):
            weighted_risk_signal(0.8, None, context)


class DatasetHistoryContractTests(unittest.TestCase):
    def test_all_records_have_boolean_flag_and_both_paths_are_covered(self):
        data = json.loads((Path(__file__).parents[1] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        contexts = [prepare_history_context(item) for item in data["patients"]]
        self.assertEqual(sum(item["history_missingness_indicator"] for item in contexts), 10)
        self.assertEqual(sum(item["has_prior_history_feature"] for item in contexts), 10)


if __name__ == "__main__":
    unittest.main()

