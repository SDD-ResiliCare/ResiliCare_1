import unittest

from src import evaluate_safety_rules, get_age_profile, normalize_vitals, prepare_patient_vitals


def case(age, **vitals):
    return {
        "age_years": age, "hr_bpm": 80, "rr_bpm": 16, "spo2_pct": 98,
        "sbp_mmhg": 120, "dbp_mmhg": 75, "temp_c": 36.8,
        "immediate_lifesaving_intervention": False, "high_risk_presentation": False,
        "ambiguity_flag": False,
    } | vitals


class AgeProfilesTests(unittest.TestCase):
    def test_requested_age_brackets_are_covered_without_gaps(self):
        expected = {
            0: "neonate", 0.25: "infant", 1: "toddler", 3: "child",
            12: "adolescent", 18: "adult", 65: "geriatric",
        }
        for age, bracket in expected.items():
            with self.subTest(age=age):
                self.assertEqual(get_age_profile(age)["bracket"], bracket)

    def test_child_profiles_are_finer_than_one_broad_range(self):
        self.assertEqual(get_age_profile(4)["id"], "child_4y")
        self.assertEqual(get_age_profile(10)["id"], "child_10y")

    def test_geriatric_uses_adult_news2_band_but_requires_baseline_context(self):
        adult, older = get_age_profile(40), get_age_profile(70)
        self.assertEqual(adult["hr_bpm"], older["hr_bpm"])
        self.assertTrue(older["requires_baseline_context"])

    def test_invalid_age_is_rejected(self):
        for age in (-1, 130, None, float("nan"), float("inf")):
            with self.subTest(age=age), self.assertRaises(ValueError):
                get_age_profile(age)


class NormalizationTests(unittest.TestCase):
    def test_same_heart_rate_is_interpreted_by_age(self):
        neonate = normalize_vitals(case(0.1, hr_bpm=130))["values"]["hr_bpm"]
        adult = normalize_vitals(case(30, hr_bpm=130))["values"]["hr_bpm"]
        self.assertEqual(neonate["status"], "WITHIN")
        self.assertEqual(adult["status"], "HIGH")
        self.assertGreater(adult["signed_deviation"], 0)

    def test_signed_deviation_is_zero_inside_and_negative_below(self):
        result = normalize_vitals(case(30, hr_bpm=50))["values"]
        self.assertEqual(result["rr_bpm"]["signed_deviation"], 0)
        self.assertLess(result["hr_bpm"]["signed_deviation"], 0)

    def test_missing_values_remain_explicit(self):
        result = normalize_vitals(case(8, spo2_pct=None))["values"]["spo2_pct"]
        self.assertEqual((result["status"], result["signed_deviation"]), ("MISSING", None))

    def test_normalized_signal_reaches_safety_layer(self):
        result = evaluate_safety_rules(case(0.1, hr_bpm=100))
        self.assertEqual(result["age_adjusted_vitals"]["age_bracket"], "neonate")
        self.assertIn("REVIEW.BORDERLINE_VITALS", result["matched_rule_ids"])
        self.assertEqual(result["provisional_esi"], 3)

    def test_preparation_does_not_mutate_input(self):
        original = case(30)
        prepared = prepare_patient_vitals(original)
        self.assertNotIn("vital_deviations", original)
        self.assertIn("vital_deviations", prepared)


if __name__ == "__main__":
    unittest.main()
