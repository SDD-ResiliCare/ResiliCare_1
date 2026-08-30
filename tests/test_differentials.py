import json
import unittest
from pathlib import Path

from resilicare import (
    apply_safety_ceiling,
    evaluate_safety_rules,
    load_ambiguous_presentation_table,
    match_ambiguous_presentations,
    score_with_confidence,
)


def patient(**changes):
    base = {
        "age_years": 40, "chief_complaint": "Minor skin irritation", "presenting_details": "",
        "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 99, "sbp_mmhg": 120,
        "dbp_mmhg": 75, "temp_c": 36.8, "has_prior_history": True,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    }
    return base | changes


class AmbiguousPresentationTests(unittest.TestCase):
    def test_chest_discomfort_forces_esi_three_ceiling_even_with_mild_vitals(self):
        case = patient(chief_complaint="Central chest burning after dinner")
        safety = evaluate_safety_rules(case)
        self.assertEqual(safety["maximum_allowed_esi"], 3)
        self.assertEqual(apply_safety_ceiling(5, safety), 3)
        self.assertEqual(apply_safety_ceiling(2, safety), 2)
        self.assertIn("REVIEW.DIFFERENTIAL.ACUTE_CHEST_DISCOMFORT", safety["matched_rule_ids"])

    def test_chest_pathway_returns_differential_and_required_actions(self):
        match = match_ambiguous_presentations(patient(chief_complaint="Chest pain"))[0]
        self.assertTrue(match["mandatory_safety_workup"])
        self.assertIn("acute coronary syndrome", match["differential_considerations"])
        self.assertIn("12-lead ECG", match["required_safety_actions"])
        self.assertTrue(any("troponin" in action for action in match["required_safety_actions"]))

    def test_match_is_phrase_bounded_and_does_not_diagnose(self):
        self.assertEqual(match_ambiguous_presentations(patient(chief_complaint="Chestnut allergy")), [])
        self.assertEqual(match_ambiguous_presentations(patient(presenting_details="Denies syncope")), [])
        match = match_ambiguous_presentations(patient(chief_complaint="Near syncope"))[0]
        self.assertEqual(match["pathway_id"], "SYNCOPE_OR_NEAR_SYNCOPE")
        self.assertNotIn("diagnosis", match)

    def test_all_matching_pathways_are_returned_and_most_urgent_rule_still_wins(self):
        case = patient(chief_complaint="Chest pain after fainting", immediate_lifesaving_intervention=True)
        safety = evaluate_safety_rules(case)
        self.assertEqual(safety["provisional_esi"], 1)
        self.assertEqual(len(safety["ambiguous_presentations"]), 2)

    def test_confidence_output_and_explanation_expose_workup(self):
        result = score_with_confidence(patient(chief_complaint="Chest pressure"), 5)
        self.assertEqual(result["point_estimate"], 3)
        self.assertTrue(result["mandatory_safety_workup"])
        self.assertIn("12-lead ECG", result["explanation_text"])
        self.assertIn("AMBIGUOUS_PRESENTATION", result["uncertainty_reasons"])

    def test_table_is_small_versioned_and_sourced(self):
        table = load_ambiguous_presentation_table()
        self.assertEqual(table["schema_version"], 1)
        self.assertIn(len(table["entries"]), range(1, 6))
        self.assertTrue(all(entry["source_urls"] for entry in table["entries"]))


class DatasetContractTests(unittest.TestCase):
    def test_round_one_ambiguous_chest_case_hits_pathway(self):
        dataset = json.loads((Path(__file__).parents[1] / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
        case = next(item for item in dataset["patients"] if item["patient_id"] == "PT-004")
        result = score_with_confidence(case, case["reference_esi"])
        self.assertTrue(result["mandatory_safety_workup"])
        self.assertEqual(result["ambiguous_presentations"][0]["pathway_id"], "ACUTE_CHEST_DISCOMFORT")


if __name__ == "__main__":
    unittest.main()
