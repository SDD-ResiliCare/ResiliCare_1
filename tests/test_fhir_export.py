import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from resilicare import FHIR_SHAPED_DISCLAIMER, build_fhir_shaped_bundle, validate_fhir_shaped_bundle  # noqa: E402


class FhirExportTests(unittest.TestCase):
    def test_bundle_has_linked_patient_encounter_and_vital_observations(self):
        seed = json.loads((ROOT / "data" / "resilicare_history_seed.json").read_text(encoding="utf-8"))
        patient, encounter = seed["patients"]["RC-P-016"], seed["encounters"][0]
        bundle = build_fhir_shaped_bundle(patient, encounter)
        resources = [entry["resource"] for entry in bundle["entry"]]
        self.assertEqual(bundle["resourceType"], "Bundle")
        self.assertEqual([r["resourceType"] for r in resources[:2]], ["Patient", "Encounter"])
        self.assertEqual(len([r for r in resources if r["resourceType"] == "Observation"]), 6)
        self.assertEqual(resources[1]["subject"]["reference"], "Patient/RC-P-016")
        self.assertTrue(all(r["encounter"]["reference"] == "Encounter/RC-E-016-20240815"
                            for r in resources[2:]))
        self.assertEqual(bundle["extension"][0]["valueString"], FHIR_SHAPED_DISCLAIMER)
        extension_urls = {extension["url"] for extension in resources[1]["extension"]}
        self.assertIn("https://resilicare.local/confidence-score", extension_urls)
        self.assertIn("https://resilicare.local/score-explanation", extension_urls)
        validate_fhir_shaped_bundle(bundle)

    def test_missing_vital_is_not_fabricated(self):
        seed = json.loads((ROOT / "data" / "resilicare_history_seed.json").read_text(encoding="utf-8"))
        encounter = dict(seed["encounters"][0])
        encounter["vitals"] = dict(encounter["vitals"], spo2_pct=None)
        bundle = build_fhir_shaped_bundle(seed["patients"]["RC-P-016"], encounter)
        ids = [x["resource"]["id"] for x in bundle["entry"] if x["resource"]["resourceType"] == "Observation"]
        self.assertNotIn("RC-E-016-20240815-spo2_pct", ids)

    def test_structural_validator_rejects_broken_patient_reference(self):
        seed = json.loads((ROOT / "data" / "resilicare_history_seed.json").read_text(encoding="utf-8"))
        bundle = build_fhir_shaped_bundle(seed["patients"]["RC-P-016"], seed["encounters"][0])
        bundle["entry"][1]["resource"]["subject"]["reference"] = "Patient/wrong"
        with self.assertRaises(ValueError):
            validate_fhir_shaped_bundle(bundle)


if __name__ == "__main__":
    unittest.main()
