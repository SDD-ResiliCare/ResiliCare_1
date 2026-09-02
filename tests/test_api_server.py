import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from src.api.server import create_server  # noqa: E402


class AuditServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name) / "audit.jsonl"
        self.history = Path(self.temp.name) / "history.json"
        self.server = create_server(ROOT, self.log, port=0, history_path=self.history)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None):
        body = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            self.base + path, data=body, method=method,
            headers={"Content-Type": "application/json"} if body else {},
        )
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())

    def test_override_http_flow_uses_server_canonical_ai_snapshot(self):
        _, suggestions = self.request("/api/hospital/suggestions")
        self.assertEqual(len(suggestions), 20)
        suggestion = suggestions[0]
        original = suggestion["ai_result"]["point_estimate"]
        overridden = 2 if original != 2 else 3
        status, event = self.request("/api/hospital/overrides", "POST", {
            "patient_id": suggestion["patient_id"], "clinician_id": "NURSE-7", "clinician_role": "RN",
            "overridden_esi": overridden, "reason_code": "EXAMINATION_FINDINGS",
            "reason_text": "Focused examination changed clinical concern.",
            "original_ai": {"point_estimate": 5, "confidence_score": 1.0},
        })
        self.assertEqual(status, 201)
        self.assertEqual(event["original_ai"]["point_estimate"], original)
        _, ledger = self.request("/api/hospital/audit")
        self.assertEqual(ledger[-1]["event_id"], event["event_id"])

    def test_update_and_delete_endpoints_do_not_exist(self):
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method), self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("/api/hospital/audit", method, {})
            self.assertEqual(raised.exception.code, 405)
            raised.exception.close()

    def test_live_hospital_profile_swap_changes_operations_not_esi(self):
        _, profiles = self.request("/api/hospital/profiles")
        self.assertEqual(profiles["active_profile_id"], "urban_trauma_center")
        self.assertEqual({item["profile_id"] for item in profiles["profiles"]},
                         {"urban_trauma_center", "rural_clinic"})
        _, urban = self.request("/api/hospital/queue")
        urban_case = next(item for item in urban["items"] if item["source_patient_id"] == "PT-009")
        self.assertEqual(urban_case["hospital_operations"]["status"], "LOCAL_CARE_AVAILABLE")
        _, rural = self.request("/api/hospital/profile", "POST", {"profile_id": "rural_clinic"})
        self.assertTrue(rural["combat_mode"]["active"])
        rural_case_id = urban_case["patient_id"]
        self.request("/api/hospital/combat-acknowledge", "POST", {
            "patient_id": rural_case_id, "clinician_id": "NURSE-11", "clinician_role": "RN",
        })
        _, rural = self.request("/api/hospital/queue")
        rural_case = next(item for item in rural["items"] if item["patient_id"] == urban_case["patient_id"])
        self.assertEqual(rural_case["ai_result"], urban_case["ai_result"])
        self.assertEqual(rural_case["queue"], urban_case["queue"])
        self.assertEqual(rural_case["hospital_operations"]["status"], "TRANSFER_RECOMMENDED")
        self.assertIn("general_surgery", rural_case["hospital_operations"]["unavailable_specialties"])
        self.assertTrue(rural_case["hospital_operations"]["capacity_warning"])
        self.assertTrue(rural_case["hospital_operations"]["clinical_priority_unchanged"])

    def test_unknown_hospital_profile_is_rejected_without_changing_active_profile(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/hospital/profile", "POST", {"profile_id": "unknown"})
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        _, profiles = self.request("/api/hospital/profiles")
        self.assertEqual(profiles["active_profile_id"], "urban_trauma_center")

    def test_returning_patient_history_and_fhir_shaped_export(self):
        _, quiet = self.request("/api/hospital/queue")
        item = next(x for x in quiet["items"] if x["source_patient_id"] == "PT-016")
        self.assertEqual(item["patient_uid"], "RC-P-016")
        _, history = self.request(
            f"/api/patient/history?patient_uid={item['patient_uid']}&current_encounter_id={item['encounter_id']}"
        )
        self.assertEqual(history["label"], "History from previous ResiliCare visits only")
        self.assertFalse(history["complete_ehr_history"])
        self.assertEqual(history["visits"][0]["final_clinician_decision"]["decision"], "accepted")
        _, exported = self.request(f"/api/hospital/fhir-export?encounter_id={item['encounter_id']}")
        self.assertIn("not validated", exported["disclaimer"])
        types = [entry["resource"]["resourceType"] for entry in exported["bundle"]["entry"]]
        self.assertEqual(types[:2], ["Patient", "Encounter"])
        self.assertIn("Observation", types)

    def test_override_updates_current_encounter_history(self):
        _, quiet = self.request("/api/hospital/queue")
        item = quiet["items"][0]
        point = item["ai_result"]["point_estimate"]
        overridden = 2 if point != 2 else 3
        _, event = self.request("/api/hospital/overrides", "POST", {
            "patient_id": item["patient_id"], "clinician_id": "NURSE-16", "clinician_role": "RN",
            "overridden_esi": overridden, "reason_code": "AI_DISAGREEMENT", "reason_text": "Exam differs.",
        })
        stored = json.loads(self.history.read_text(encoding="utf-8"))
        encounter = next(x for x in stored["encounters"] if x["encounter_id"] == item["encounter_id"])
        self.assertEqual(encounter["final_clinician_decision"]["audit_event_id"], event["event_id"])

    def test_three_x_surge_automatically_triggers_combat_mode_at_twenty(self):
        _, quiet = self.request("/api/hospital/queue")
        self.assertEqual(quiet["queue_length"], 7)
        self.assertFalse(quiet["combat_mode"]["active"])
        _, surge = self.request("/api/hospital/surge/run", "POST", {})
        self.assertEqual(surge["queue_length"], 21)
        self.assertEqual(surge["combat_mode"]["threshold"], 20)
        self.assertEqual(surge["combat_mode"]["trigger"], "QUEUE_LENGTH")
        self.assertFalse(surge["combat_mode"]["scoring_changed"])
        quiet_second = next(item for item in quiet["items"] if item["patient_id"] == "Q-002")
        self.request("/api/hospital/combat-acknowledge", "POST", {
            "patient_id": "Q-002", "clinician_id": "NURSE-12", "clinician_role": "RN",
        })
        _, surge = self.request("/api/hospital/queue")
        surge_second = next(item for item in surge["items"] if item["patient_id"] == "Q-002")
        self.assertEqual(quiet_second["ai_result"], surge_second["ai_result"])

    def test_manual_surge_works_below_threshold(self):
        _, result = self.request("/api/hospital/surge/manual", "POST", {"active": True})
        self.assertEqual(result["queue_length"], 7)
        self.assertEqual(result["combat_mode"]["trigger"], "MANUAL")

    def test_combat_acknowledgement_uses_canonical_snapshot_and_is_logged(self):
        _, surge = self.request("/api/hospital/surge/run", "POST", {})
        item = surge["items"][0]
        status, result = self.request("/api/hospital/combat-acknowledge", "POST", {
            "patient_id": item["patient_id"], "clinician_id": "NURSE-14", "clinician_role": "RN",
            "current_ai": {"point_estimate": 5, "confidence_score": 0},
        })
        self.assertEqual(status, 201)
        event = result["event"]
        self.assertEqual(event["current_ai"]["point_estimate"], result["patient"]["ai_result"]["point_estimate"])
        self.assertEqual(event["safety_badge"], result["patient"]["safety_badge"])
        self.assertEqual(event["surge_state"]["trigger"], "QUEUE_LENGTH")
        _, ledger = self.request("/api/hospital/audit")
        self.assertEqual(ledger[-1]["event_id"], event["event_id"])

    def test_suggestions_expose_scheme_and_safety_gated_routing(self):
        _, suggestions = self.request("/api/hospital/suggestions")
        by_id = {item["patient_id"]: item for item in suggestions}
        self.assertEqual(by_id["PT-016"]["scheme"], "ESIC")
        self.assertEqual(by_id["PT-016"]["routing_assessment"]["status"], "CLINICIAN_CONFIRMATION_REQUIRED")
        self.assertEqual(by_id["PT-015"]["routing_assessment"]["status"], "CLINICAL_ROUTING_BLOCKED")
        self.assertEqual(by_id["PT-004"]["routing_assessment"]["status"], "NOT_LOW_ACUITY")

    def test_route_preview_uses_canonical_score_and_returns_fictional_esic_route(self):
        self.request("/api/hospital/confirmations", "POST", {
            "patient_id": "PT-016", "clinician_id": "NURSE-16", "clinician_role": "RN",
        })
        status, result = self.request("/api/patient/routing-preview", "POST", {
            "patient_id": "PT-016", "confirmed_esi": 5, "scheme": "Self-pay",
        })
        self.assertEqual(status, 200)
        self.assertEqual(result["confirmed_esi"], 4)
        self.assertEqual(result["scheme"], "ESIC")
        self.assertEqual(result["status"], "ROUTE_SUGGESTED")
        self.assertTrue(result["recommended_route"]["cashless_eligible"])
        self.assertEqual(result["recommended_route"]["facility_name"], "SevaSetu ESIC Fast-Track Clinic")
        self.assertFalse(result["live_nhcx_integration"])

    def test_confirmation_requires_clinician_role_and_is_server_enforced(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/hospital/confirmations", "POST", {"patient_id": "PT-016", "clinician_id": "NURSE-16"})
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()
        _, pending = self.request("/api/patient/routing-preview", "POST", {"patient_id": "PT-016"})
        self.assertEqual(pending["status"], "CLINICIAN_CONFIRMATION_REQUIRED")
        _, confirmation = self.request("/api/hospital/confirmations", "POST", {
            "patient_id": "PT-016", "clinician_id": "NURSE-16", "clinician_role": "RN",
        })
        self.assertEqual(confirmation["clinical_confirmation"]["status"], "CONFIRMED")
        self.assertEqual(confirmation["event"]["clinician_role"], "RN")

    def test_vital_update_retriages_and_retracts_confirmed_low_acuity_route(self):
        _, queue = self.request("/api/hospital/queue")
        candidate = next(item for item in queue["items"] if item["routing_assessment"]["status"] == "CLINICIAN_CONFIRMATION_REQUIRED")
        self.request("/api/hospital/confirmations", "POST", {
            "patient_id": candidate["patient_id"], "clinician_id": "NURSE-17", "clinician_role": "RN",
        })
        _, before = self.request("/api/patient/routing-preview", "POST", {"patient_id": candidate["patient_id"]})
        self.assertEqual(before["status"], "ROUTE_SUGGESTED")
        _, updated = self.request("/api/hospital/queue/vitals", "POST", {
            "patient_id": candidate["patient_id"], "vitals": {"hr_bpm": 140, "spo2_pct": 89},
            "observed_at": candidate["queue"]["entered_at"],
        })
        after = next(item for item in updated["items"] if item["patient_id"] == candidate["patient_id"])
        self.assertNotEqual(after["clinical_confirmation"]["status"], "CONFIRMED")
        self.assertNotEqual(after["routing_assessment"]["status"], "ROUTE_SUGGESTED")

    def test_evidence_and_compliance_exports_are_redacted_and_profile_comparable(self):
        _, evidence = self.request("/api/hospital/surge/evidence")
        self.assertEqual(evidence["quiet_before"]["queue_length"], 7)
        self.assertEqual(evidence["surge_after"]["queue_length"], 21)
        self.assertTrue(evidence["surge_after"]["combat_mode"]["active"])
        _, comparison = self.request("/api/hospital/profile-comparison?patient_id=Q-007")
        self.assertEqual(len(comparison["comparison"]), 2)
        self.assertEqual({item["esi_unchanged"] for item in comparison["comparison"]}, {3})
        _, compliance = self.request("/api/hospital/audit/compliance-export")
        self.assertTrue(compliance["integrity"]["valid"])
        self.assertNotIn("patient_id", compliance["events"][0])
        self.assertIn("patient_pseudonym", compliance["events"][0])

    def test_route_preview_keeps_uncertain_case_blocked(self):
        _, result = self.request("/api/patient/routing-preview", "POST", {"patient_id": "PT-015"})
        self.assertEqual(result["status"], "CLINICAL_ROUTING_BLOCKED")
        self.assertEqual(result["suggestions"], [])

    def test_kiosk_status_reports_missing_optional_nlp_dependencies(self):
        status, result = self.request("/api/patient/kiosk-status")
        self.assertEqual(status, 200)
        self.assertIn("audio_pipeline_available", result)
        self.assertIsInstance(result["missing_dependencies"], list)

    def test_kiosk_text_extracts_complaint_and_previews_differential_table_only(self):
        status, result = self.request("/api/patient/kiosk-text", "POST", {"transcript": "seene mein dard ho raha hai"})
        self.assertEqual(status, 200)
        self.assertTrue(result["confidence_gate_passed"])
        self.assertEqual(result["extracted_complaint"], "chest pain")
        self.assertEqual(result["differential_matches"][0]["pathway_id"], "ACUTE_CHEST_DISCOMFORT")
        self.assertTrue(result["experimental"])
        # Preview only: no queue/audit side effects from a kiosk transcript.
        _, before = self.request("/api/hospital/audit")
        self.request("/api/patient/kiosk-text", "POST", {"transcript": "seene mein dard ho raha hai"})
        _, after = self.request("/api/hospital/audit")
        self.assertEqual(after, before)

    def test_kiosk_text_negation_suppresses_the_red_flag(self):
        _, result = self.request("/api/patient/kiosk-text", "POST", {
            "transcript": "I am not bleeding profusely, just tired",
        })
        self.assertEqual(result["clinical_acuity_red_flags"], [])

    def test_kiosk_text_rejects_empty_transcript(self):
        with self.assertRaises(urllib.error.HTTPError) as raised:
            self.request("/api/patient/kiosk-text", "POST", {"transcript": "  "})
        self.assertEqual(raised.exception.code, 400)
        raised.exception.close()


if __name__ == '__main__':
    unittest.main()

