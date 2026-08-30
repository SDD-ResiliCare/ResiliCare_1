import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from resilicare import (  # noqa: E402
    initialize_history_store, load_simulated_patients, patient_uid_for_source,
    previous_visits, record_history_override, score_with_confidence,
    upsert_current_encounter,
)
from resilicare.combat import critical_safety_badge  # noqa: E402


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "history.json"
        initialize_history_store(ROOT / "data" / "resilicare_history_seed.json", self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_stable_patient_and_encounter_are_separate_and_support_repeat_visits(self):
        patient = load_simulated_patients(ROOT / "data" / "simulated_patients.json")[15]
        result = score_with_confidence(patient, patient["reference_esi"])
        encounter = upsert_current_encounter(
            self.path, patient=patient, ai_result=result,
            safety_badge=critical_safety_badge(result), encounter_id="PT-016",
            patient_uid=patient_uid_for_source("PT-016"),
        )
        self.assertEqual(encounter["patient_uid"], "RC-P-016")
        self.assertEqual(encounter["encounter_id"], "PT-016")
        visits = previous_visits(self.path, "RC-P-016", "PT-016")
        self.assertEqual([visit["encounter_id"] for visit in visits], ["RC-E-016-20240815"])

    def test_initialization_never_overwrites_runtime_and_override_is_mirrored(self):
        store = json.loads(self.path.read_text(encoding="utf-8"))
        store["marker"] = "keep"
        self.path.write_text(json.dumps(store), encoding="utf-8")
        initialize_history_store(ROOT / "data" / "resilicare_history_seed.json", self.path)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8"))["marker"], "keep")
        event = {
            "overridden_esi": 3, "clinician_id": "NURSE-1", "timestamp": "2026-08-30T00:00:00Z",
            "reason": {"code": "AI_DISAGREEMENT", "label": "Clinician disagrees", "free_text": "Exam"},
            "event_id": "event-1",
        }
        updated = record_history_override(self.path, "RC-E-016-20240815", event)
        self.assertEqual(updated["final_clinician_decision"]["final_esi"], 3)
        self.assertEqual(updated["final_clinician_decision"]["audit_event_id"], "event-1")


if __name__ == "__main__":
    unittest.main()
