"""Dependency-free local demo server for override capture and audit viewing."""

from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from resilicare import REASON_CODES, read_audit_events, record_clinician_override, score_with_confidence  # noqa: E402


def build_demo_suggestions(project_root: Path) -> dict[str, dict]:
    dataset = json.loads((project_root / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
    suggestions = {}
    for patient in dataset["patients"]:
        result = score_with_confidence(patient, int(patient["reference_esi"]))
        suggestions[patient["patient_id"]] = {
            "patient_id": patient["patient_id"], "age_years": patient["age_years"],
            "chief_complaint": patient["chief_complaint"], "ai_result": result,
            "score_source": "SYNTHETIC_REFERENCE_STUB_FOR_UI_DEMO",
        }
    return suggestions


def create_server(
    project_root: Path = PROJECT_ROOT,
    log_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    suggestions = build_demo_suggestions(project_root)
    audit_path = log_path or project_root / "data" / "audit_log.jsonl"
    page = (project_root / "demo" / "index.html").read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif parsed.path == "/api/suggestions":
                self._json(200, list(suggestions.values()))
            elif parsed.path == "/api/reasons":
                self._json(200, REASON_CODES)
            elif parsed.path == "/api/audit":
                patient_id = parse_qs(parsed.query).get("patient_id", [None])[0]
                self._json(200, read_audit_events(audit_path, patient_id=patient_id))
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            if urlparse(self.path).path != "/api/overrides":
                return self._json(404, {"error": "not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 65536:
                    raise ValueError("request body must be between 1 and 65536 bytes")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                suggestion = suggestions.get(payload.get("patient_id"))
                if not suggestion:
                    return self._json(404, {"error": "unknown patient_id"})
                event = record_clinician_override(
                    audit_path, patient_id=suggestion["patient_id"], clinician_id=payload.get("clinician_id", ""),
                    original_ai_result=suggestion["ai_result"], overridden_esi=payload.get("overridden_esi"),
                    reason_code=payload.get("reason_code", ""), reason_text=payload.get("reason_text", ""),
                )
                self._json(201, event)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def do_PUT(self): self._method_not_allowed()
        def do_PATCH(self): self._method_not_allowed()
        def do_DELETE(self): self._method_not_allowed()

        def _method_not_allowed(self):
            self._json(405, {"error": "audit records are append-only; update and delete are not supported"})

        def _json(self, status, value):
            self._send(status, json.dumps(value, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log", type=Path, default=PROJECT_ROOT / "data" / "audit_log.jsonl")
    args = parser.parse_args()
    server = create_server(log_path=args.log, host=args.host, port=args.port)
    print(f"ResiliCare audit demo: http://{args.host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
