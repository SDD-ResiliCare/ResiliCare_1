"""ResiliCare API Server."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.api.state import ServerState
import src.api.routes.hospital as hospital_routes
import src.api.routes.patient as patient_routes


class APIRouter:
    def __init__(self, state: ServerState):
        self.state = state
        self.routes = {
            "GET": {
                "/api/hospital/suggestions": hospital_routes.get_suggestions,
                "/api/hospital/queue": hospital_routes.get_queue,
                "/api/hospital/reasons": hospital_routes.get_reasons,
                "/api/hospital/profiles": hospital_routes.get_hospital_profiles,
                "/api/hospital/audit": hospital_routes.get_audit,
                "/api/hospital/audit/compliance-export": hospital_routes.get_compliance_export,
                "/api/patient/history": patient_routes.get_history,
                "/api/patient/kiosk-status": patient_routes.get_kiosk_status,
                "/api/hospital/fhir-export": hospital_routes.get_fhir_export,
                "/api/hospital/override-rates": hospital_routes.get_override_rates,
                "/api/hospital/surge/evidence": hospital_routes.get_surge_evidence,
                "/api/hospital/profile-comparison": hospital_routes.get_profile_comparison,
            },
            "POST": {
                "/api/hospital/surge/run": hospital_routes.post_surge_run,
                "/api/hospital/surge/reset": hospital_routes.post_surge_reset,
                "/api/hospital/surge/manual": hospital_routes.post_surge_manual,
                "/api/hospital/profile": hospital_routes.post_hospital_profile,
                "/api/hospital/confirmations": hospital_routes.post_confirmation,
                "/api/hospital/queue/vitals": hospital_routes.post_queue_vitals,
                "/api/patient/kiosk-text": patient_routes.post_kiosk_text,
                "/api/hospital/combat-acknowledge": hospital_routes.post_combat_acknowledge,
                "/api/patient/routing-preview": patient_routes.post_routing_preview,
                "/api/hospital/overrides": hospital_routes.post_overrides,
            }
        }

    def handle(self, method: str, path: str, query: dict, payload: dict | None) -> tuple[int, dict]:
        if path == "/":
            return 200, {
                "message": "ResiliCare API Server is running.",
                "namespaces": {
                    "hospital_facing": {
                        "GET": list(self.routes["GET"].keys()),
                        "POST": [p for p in self.routes["POST"].keys() if p.startswith("/api/hospital")]
                    },
                    "patient_facing": {
                        "GET": [p for p in self.routes["GET"].keys() if p.startswith("/api/patient")],
                        "POST": [p for p in self.routes["POST"].keys() if p.startswith("/api/patient")]
                    }
                }
            }

        handlers = self.routes.get(method)
        if not handlers:
            return 405, {"error": "method not allowed"}
            
        handler = handlers.get(path)
        if not handler:
            return 404, {"error": "not found"}
            
        try:
            if method == "GET":
                return handler(self.state, query)
            else:
                return handler(self.state, payload)
        except Exception as exc:
            return 400, {"error": str(exc)}


def create_server(
    project_root: Path,
    log_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    history_path: Path | None = None,
    confirmation_timeout_seconds: int = 15 * 60,
) -> ThreadingHTTPServer:
    if type(confirmation_timeout_seconds) is not int or confirmation_timeout_seconds < 1:
        raise ValueError("confirmation_timeout_seconds must be a positive integer")
    
    log_path = log_path or project_root / "data" / "audit_log.jsonl"
    state = ServerState(project_root, log_path, history_path, confirmation_timeout_seconds)
    router = APIRouter(state)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            status, response = router.handle("GET", parsed.path, query, None)
            self._json(status, response)

        def do_POST(self):
            parsed = urlparse(self.path)
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 65536:
                    raise ValueError("request body must be between 1 and 65536 bytes")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                status, response = router.handle("POST", parsed.path, {}, payload)
                self._json(status, response)
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
    project_root = Path(__file__).parents[2]
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log", type=Path, default=project_root / "data" / "audit_log.jsonl")
    args = parser.parse_args()
    
    server = create_server(project_root=project_root, log_path=args.log, host=args.host, port=args.port)
    print(f"ResiliCare audit demo: http://{args.host}:{server.server_port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
