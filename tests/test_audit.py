import json
import tempfile
import unittest
from pathlib import Path

from src import append_audit_event, read_audit_events, record_clinician_override, verify_audit_chain


def ai_result(point=3):
    return {
        "display_score": f"ESI {point}", "point_estimate": point, "esi_set": [point],
        "confidence_score": 0.82, "confidence_label": "Moderate",
        "confidence_method": "evidence_completeness_heuristic",
        "badge": f"ESI {point} — Moderate confidence",
        "explanation_text": f"ESI {point} — test explanation.",
        "explanation_rule_ids": ["TEST.RULE"],
        "mandatory_safety_workup": True,
        "ambiguous_presentations": [{"pathway_id": "TEST_PATHWAY"}],
    }


class OverrideAuditTests(unittest.TestCase):
    def test_override_captures_required_snapshot_and_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            event = record_clinician_override(
                log, patient_id="PT-009", clinician_id="NURSE-7", clinician_role="RN", original_ai_result=ai_result(),
                overridden_esi=2, reason_code="CLINICAL_DETERIORATION", reason_text="New diaphoresis and increasing pain.",
            )
            stored = read_audit_events(log)[0]
        self.assertEqual(stored, event)
        self.assertEqual(stored["original_ai"]["confidence_score"], 0.82)
        self.assertEqual(stored["original_ai"]["explanation_rule_ids"], ["TEST.RULE"])
        self.assertTrue(stored["original_ai"]["mandatory_safety_workup"])
        self.assertEqual(stored["original_ai"]["ambiguous_presentations"][0]["pathway_id"], "TEST_PATHWAY")
        self.assertEqual(stored["overridden_esi"], 2)
        self.assertEqual(stored["override_direction"], "escalation")
        self.assertEqual(stored["clinician_role"], "RN")
        self.assertTrue(stored["event_id"])
        self.assertTrue(stored["timestamp"].endswith("+00:00"))

    def test_dropdown_and_free_text_are_both_required(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            for code, text in (("", "detail"), ("OTHER", ""), ("INVALID", "detail")):
                with self.subTest(code=code, text=text), self.assertRaises(ValueError):
                    record_clinician_override(
                        log, patient_id="PT-009", clinician_id="N1", clinician_role="RN", original_ai_result=ai_result(),
                        overridden_esi=2, reason_code=code, reason_text=text,
                    )

    def test_same_score_is_not_an_override(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            record_clinician_override(
                Path(directory) / "audit.jsonl", patient_id="PT-009", clinician_id="N1", clinician_role="RN",
                original_ai_result=ai_result(3), overridden_esi=3,
                reason_code="AI_DISAGREEMENT", reason_text="No score change.",
            )

    def test_ledger_is_insert_only_and_filterable(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            append_audit_event(log, "first", "PT-1", {"value": 1})
            append_audit_event(log, "second", "PT-2", {"value": 2})
            lines = log.read_text(encoding="utf-8").splitlines()
            filtered = read_audit_events(log, patient_id="PT-2")
        self.assertEqual(len(lines), 2)
        self.assertEqual(filtered[0]["event_type"], "second")
        self.assertTrue(verify_audit_chain(log)["valid"])

    def test_role_is_required_and_hash_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "audit.jsonl"
            with self.assertRaises(ValueError):
                record_clinician_override(
                    log, patient_id="PT-009", clinician_id="N1", clinician_role="ADMIN", original_ai_result=ai_result(),
                    overridden_esi=2, reason_code="OTHER", reason_text="Role is not clinical.",
                )
            append_audit_event(log, "first", "PT-1", {"value": 1})
            event = read_audit_events(log)[0]
            log.write_text(json.dumps(event | {"value": 2}) + "\n", encoding="utf-8")
            self.assertFalse(verify_audit_chain(log)["valid"])

    def test_reserved_ledger_fields_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(ValueError):
            append_audit_event(Path(directory) / "audit.jsonl", "test", "PT-1", {"timestamp": "forged"})


if __name__ == "__main__":
    unittest.main()

