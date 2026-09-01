import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src import assess_hospital_operations, load_hospital_profiles  # noqa: E402


class HospitalConfigTests(unittest.TestCase):
    def setUp(self):
        self.abdominal = {"patient_id": "PT-009", "age_years": 35, "chief_complaint": "Right lower abdominal pain"}
        self.ai = {"point_estimate": 3, "badge": "ESI 3 — High confidence"}

    def test_profiles_externalize_required_capabilities(self):
        profiles = load_hospital_profiles()["profiles"]
        urban, rural = profiles["urban_trauma_center"], profiles["rural_clinic"]
        self.assertIn("cardiology", urban["available_specialties"])
        self.assertIn("pediatrics", urban["available_specialties"])
        self.assertIn("trauma", urban["available_specialties"])
        self.assertTrue(urban["icu_available"])
        self.assertFalse(rural["icu_available"])
        self.assertEqual(rural["bed_counts"]["icu"], 0)
        self.assertTrue(rural["transfer_capability"]["transfer_first_for_unsupported"])

    def test_same_patient_keeps_esi_but_changes_operational_recommendation(self):
        original = copy.deepcopy(self.ai)
        urban = assess_hospital_operations(self.abdominal, self.ai, "urban_trauma_center", queue_length=5)
        rural = assess_hospital_operations(self.abdominal, self.ai, "rural_clinic", queue_length=5)
        self.assertEqual(self.ai, original)
        self.assertEqual(urban["input_esi"], rural["input_esi"])
        self.assertTrue(urban["clinical_priority_unchanged"] and rural["clinical_priority_unchanged"])
        self.assertEqual(urban["status"], "LOCAL_CARE_AVAILABLE")
        self.assertEqual(rural["status"], "TRANSFER_RECOMMENDED")
        self.assertIn("general_surgery", rural["unavailable_specialties"])

    def test_rural_capacity_and_no_icu_are_visible_without_down_triage(self):
        patient = {"patient_id": "PT-001", "age_years": 42, "chief_complaint": "Collapsed and unresponsive",
                   "immediate_lifesaving_intervention": True}
        result = assess_hospital_operations(patient, {"point_estimate": 1}, "rural_clinic", queue_length=7)
        self.assertEqual(result["input_esi"], 1)
        self.assertTrue(result["transfer_recommended"])
        self.assertTrue(result["capacity_warning"])
        self.assertTrue(any("No on-site ICU" in alert for alert in result["alerts"]))

    def test_unknown_profile_and_invalid_queue_are_rejected(self):
        with self.assertRaises(ValueError):
            assess_hospital_operations(self.abdominal, self.ai, "mobile_hospital", queue_length=1)
        with self.assertRaises(ValueError):
            assess_hospital_operations(self.abdominal, self.ai, "rural_clinic", queue_length=-1)


if __name__ == "__main__":
    unittest.main()

