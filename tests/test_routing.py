import csv
import json
import unittest
from pathlib import Path

from resilicare import VALID_SCHEMES, load_facility_table, score_with_confidence, suggest_scheme_route

ROOT = Path(__file__).parents[1]


def dataset():
    return json.loads((ROOT / "data" / "simulated_patients.json").read_text(encoding="utf-8"))["patients"]


def patient(patient_id):
    return next(item for item in dataset() if item["patient_id"] == patient_id)


class SchemeRoutingTests(unittest.TestCase):
    def test_all_dataset_formats_have_the_same_valid_scheme_assignments(self):
        json_rows = dataset()
        with (ROOT / "data" / "simulated_patients.csv").open(encoding="utf-8-sig", newline="") as stream:
            csv_rows = list(csv.DictReader(stream))
        self.assertEqual(len(json_rows), 20)
        self.assertEqual({item["scheme"] for item in json_rows}, VALID_SCHEMES)
        self.assertEqual(
            {item["patient_id"]: item["scheme"] for item in json_rows},
            {item["patient_id"]: item["scheme"] for item in csv_rows},
        )

    def test_facilities_are_explicitly_fictional_simulated_and_offline(self):
        table = load_facility_table()
        self.assertTrue(table["simulated_data"] and table["fictional_facilities"])
        self.assertFalse(table["live_nhcx_integration"])
        self.assertTrue(all(item["fictional"] for item in table["facilities"]))

    def test_safe_esi_four_requires_confirmation_then_returns_cashless_esic_route(self):
        case = patient("PT-016")
        pending = suggest_scheme_route(case, 4, clinician_confirmed=False)
        self.assertEqual(pending["status"], "CLINICIAN_CONFIRMATION_REQUIRED")
        routed = suggest_scheme_route(case, 4, clinician_confirmed=True)
        self.assertEqual(routed["status"], "ROUTE_SUGGESTED")
        self.assertTrue(routed["recommended_route"]["cashless_eligible"])
        self.assertIn("Cashless eligible at", routed["recommended_route"]["tag"])
        self.assertGreater(routed["recommended_route"]["room_rent_cap_inr_per_day"], 0)

    def test_zero_history_uncertainty_blocks_low_acuity_routing(self):
        result = suggest_scheme_route(patient("PT-015"), 4, clinician_confirmed=True)
        self.assertEqual(result["status"], "CLINICAL_ROUTING_BLOCKED")
        self.assertIn("UNRESOLVED_ESI_UNCERTAINTY", result["blockers"])
        self.assertEqual(result["suggestions"], [])

    def test_high_acuity_patient_is_never_financially_routed(self):
        result = suggest_scheme_route(patient("PT-004"), 2, clinician_confirmed=True)
        self.assertEqual(result["status"], "NOT_LOW_ACUITY")
        self.assertTrue(result["clinical_priority_unchanged"])
        self.assertEqual(result["suggestions"], [])

    def test_scheme_never_changes_score_or_queue_inputs(self):
        original = patient("PT-016")
        changed = original | {"scheme": "Private Insurer X"}
        self.assertEqual(score_with_confidence(original, 4), score_with_confidence(changed, 4))

    def test_self_pay_is_never_labelled_cashless(self):
        case = patient("PT-016") | {"scheme": "Self-pay"}
        result = suggest_scheme_route(case, 4, clinician_confirmed=True)
        self.assertTrue(result["suggestions"])
        self.assertTrue(all(not item["cashless_eligible"] for item in result["suggestions"]))

    def test_invalid_scheme_is_rejected(self):
        with self.assertRaises(ValueError):
            suggest_scheme_route(patient("PT-016") | {"scheme": "Unknown Scheme"}, 4, clinician_confirmed=True)


if __name__ == "__main__":
    unittest.main()
