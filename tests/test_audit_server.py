import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "demo"))

from audit_server import create_server  # noqa: E402


class AuditServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.log = Path(self.temp.name) / "audit.jsonl"
        self.server = create_server(ROOT, self.log, port=0)
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
        _, suggestions = self.request("/api/suggestions")
        self.assertEqual(len(suggestions), 20)
        suggestion = suggestions[0]
        original = suggestion["ai_result"]["point_estimate"]
        overridden = 2 if original != 2 else 3
        status, event = self.request("/api/overrides", "POST", {
            "patient_id": suggestion["patient_id"], "clinician_id": "NURSE-7",
            "overridden_esi": overridden, "reason_code": "EXAMINATION_FINDINGS",
            "reason_text": "Focused examination changed clinical concern.",
            "original_ai": {"point_estimate": 5, "confidence_score": 1.0},
        })
        self.assertEqual(status, 201)
        self.assertEqual(event["original_ai"]["point_estimate"], original)
        _, ledger = self.request("/api/audit")
        self.assertEqual(ledger[0]["event_id"], event["event_id"])

    def test_update_and_delete_endpoints_do_not_exist(self):
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method), self.assertRaises(urllib.error.HTTPError) as raised:
                self.request("/api/audit", method, {})
            self.assertEqual(raised.exception.code, 405)
            raised.exception.close()

    def test_page_contains_override_control_and_log_view(self):
        with urllib.request.urlopen(self.base + "/") as response:
            page = response.read().decode()
        self.assertIn("Override AI suggestion", page)
        self.assertIn("Audit log", page)
        self.assertIn("Clinical rationale", page)
        self.assertIn("explanation", page)
        self.assertIn("Mandatory safety workup", page)
        self.assertIn("Simulated scheme data — a live NHCX integration would replace this lookup table in production.", page)
        self.assertIn("Demo: confirm ESI & show route", page)

    def test_suggestions_expose_scheme_and_safety_gated_routing(self):
        _, suggestions = self.request("/api/suggestions")
        by_id = {item["patient_id"]: item for item in suggestions}
        self.assertEqual(by_id["PT-016"]["scheme"], "ESIC")
        self.assertEqual(by_id["PT-016"]["routing_assessment"]["status"], "CLINICIAN_CONFIRMATION_REQUIRED")
        self.assertEqual(by_id["PT-015"]["routing_assessment"]["status"], "CLINICAL_ROUTING_BLOCKED")
        self.assertEqual(by_id["PT-004"]["routing_assessment"]["status"], "NOT_LOW_ACUITY")

    def test_route_preview_uses_canonical_score_and_returns_fictional_esic_route(self):
        status, result = self.request("/api/routing-preview", "POST", {
            "patient_id": "PT-016", "confirmed_esi": 5, "scheme": "Self-pay",
        })
        self.assertEqual(status, 200)
        self.assertEqual(result["confirmed_esi"], 4)
        self.assertEqual(result["scheme"], "ESIC")
        self.assertEqual(result["status"], "ROUTE_SUGGESTED")
        self.assertTrue(result["recommended_route"]["cashless_eligible"])
        self.assertEqual(result["recommended_route"]["facility_name"], "SevaSetu ESIC Fast-Track Clinic")
        self.assertFalse(result["live_nhcx_integration"])

    def test_route_preview_keeps_uncertain_case_blocked(self):
        _, result = self.request("/api/routing-preview", "POST", {"patient_id": "PT-015"})
        self.assertEqual(result["status"], "CLINICAL_ROUTING_BLOCKED")
        self.assertEqual(result["suggestions"], [])


if __name__ == "__main__":
    unittest.main()
