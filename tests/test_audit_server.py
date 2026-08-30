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


if __name__ == "__main__":
    unittest.main()
