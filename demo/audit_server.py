"""Dependency-free local demo server for override capture and audit viewing."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from resilicare import (  # noqa: E402
    FHIR_SHAPED_DISCLAIMER,
    HISTORY_SCOPE_LABEL,
    REASON_CODES,
    assess_hospital_operations,
    build_fhir_shaped_bundle,
    combat_mode_state,
    critical_safety_badge,
    encounter_with_patient,
    initialize_history_store,
    get_hospital_profile,
    load_simulated_patients,
    load_hospital_profiles,
    match_ambiguous_presentations,
    patient_uid_for_source,
    previous_visits,
    read_audit_events,
    record_combat_acknowledgement,
    record_clinician_override,
    record_history_override,
    replay_arrivals,
    score_with_confidence,
    suggest_scheme_route,
    upsert_current_encounter,
)
# EXPERIMENTAL Task 12 spike, not part of the clinical scoring path — see nlp_kiosk.py's module
# docstring and README's "Task 12" section. Imported explicitly (not via resilicare's __all__)
# so this stays visibly opt-in; the text pipeline it exposes needs no ASR/torch/spaCy deps.
from resilicare.nlp_kiosk import process_kiosk_text, resolve_kiosk_chief_complaint  # noqa: E402


def _kiosk_differential_preview(kiosk_result: dict) -> list[dict]:
    """Preview only: shows what the Task-9 differential table would say for the extracted
    complaint. Does not score a real patient or touch the queue/audit log."""
    complaint = resolve_kiosk_chief_complaint(kiosk_result)
    if not complaint:
        return []
    return match_ambiguous_presentations({"chief_complaint": complaint})


def _kiosk_audio_status() -> dict:
    """Whether the audio-in half of Task 12 (VAD/Whisper via nlp_kiosk.TriageKioskAnalyzer) can
    run in this environment. The text half (manual transcript entry) always works."""
    missing = [name for name in ("torch", "librosa", "transformers", "spacy")
               if importlib.util.find_spec(name) is None]
    return {
        "audio_pipeline_available": not missing, "missing_dependencies": missing,
        "note": "Task 12 audio intake is an experimental spike, not a demo-ready feature. "
                "Use manual transcript entry below regardless of this status.",
    }


def build_patient_suggestion(patient: dict, proposed_esi: int | None = None, queue_entry: dict | None = None) -> dict:
    result = score_with_confidence(patient, proposed_esi or int(patient["reference_esi"]))
    source_patient_id = patient.get("source_patient_id", patient["patient_id"])
    item = {
        "patient_id": patient["patient_id"], "encounter_id": patient["patient_id"],
        "source_patient_id": source_patient_id, "patient_uid": patient_uid_for_source(source_patient_id),
        "age_years": patient["age_years"], "age_group": patient.get("age_group"),
        "chief_complaint": patient["chief_complaint"], "presenting_details": patient.get("presenting_details"),
        "scheme": patient["scheme"], "patient": patient, "ai_result": result,
        "safety_badge": critical_safety_badge(result),
        "routing_assessment": suggest_scheme_route(
            patient, result["point_estimate"], clinician_confirmed=False, confidence_result=result,
        ),
        "score_source": "SYNTHETIC_REFERENCE_STUB_FOR_UI_DEMO",
    }
    if queue_entry:
        item["queue"] = {
            key: queue_entry.get(key) for key in (
                "queue_rank", "entered_at", "status", "reassessment_required", "waiting_room_alert",
            )
        }
    return item


def build_demo_suggestions(project_root: Path) -> dict[str, dict]:
    dataset = json.loads((project_root / "data" / "simulated_patients.json").read_text(encoding="utf-8"))
    suggestions = {}
    for patient in dataset["patients"]:
        suggestions[patient["patient_id"]] = build_patient_suggestion(patient)
    return suggestions


def build_queue_snapshot(patients: list[dict], multiplier: int, manually_declared: bool = False) -> dict:
    replay = replay_arrivals(patients, multiplier=multiplier, deteriorate_first_patient=multiplier == 3)
    items = [build_patient_suggestion(entry["patient"], entry["current_esi"], entry) for entry in replay["queue"]]
    return {
        "scenario": replay["scenario"], "load_multiplier": replay["load_multiplier"],
        "arrival_window_minutes": replay["arrival_window_minutes"], "queue_length": len(items),
        "deterioration_demo": replay["deterioration_demo"],
        "combat_mode": combat_mode_state(len(items), manually_declared=manually_declared),
        "items": items,
    }


def create_server(
    project_root: Path = PROJECT_ROOT,
    log_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    history_path: Path | None = None,
) -> ThreadingHTTPServer:
    dataset_path = project_root / "data" / "simulated_patients.json"
    patient_list = load_simulated_patients(dataset_path)
    suggestions = build_demo_suggestions(project_root)
    patients = {item["patient_id"]: item for item in patient_list}
    queue_lock, queue_holder = Lock(), {"snapshot": build_queue_snapshot(patient_list, 1)}
    profile_holder = {"profile_id": "urban_trauma_center"}
    audit_path = log_path or project_root / "data" / "audit_log.jsonl"
    history_runtime = initialize_history_store(
        project_root / "data" / "resilicare_history_seed.json",
        history_path or project_root / "data" / "resilicare_history_runtime.json",
    )
    page = (project_root / "demo" / "index.html").read_bytes()

    def apply_profile(items, queue_length: int, profile_id: str) -> None:
        for item in items:
            item["hospital_operations"] = assess_hospital_operations(
                item["patient"], item["ai_result"], profile_id, queue_length=queue_length,
            )

    def profile_summary(profile_id: str) -> dict:
        profile = get_hospital_profile(profile_id)
        return {"profile_id": profile_id, "display_name": profile["display_name"],
                "facility_type": profile["facility_type"], "simulated": True}

    def persist_items(items) -> None:
        for item in items:
            upsert_current_encounter(
                history_runtime, patient=item["patient"], ai_result=item["ai_result"],
                safety_badge=item["safety_badge"], encounter_id=item["encounter_id"],
                patient_uid=item["patient_uid"],
            )

    apply_profile(suggestions.values(), queue_holder["snapshot"]["queue_length"], profile_holder["profile_id"])
    apply_profile(queue_holder["snapshot"]["items"], queue_holder["snapshot"]["queue_length"], profile_holder["profile_id"])
    queue_holder["snapshot"]["hospital_profile"] = profile_summary(profile_holder["profile_id"])
    persist_items(queue_holder["snapshot"]["items"])

    def queue_snapshot() -> dict:
        with queue_lock:
            return queue_holder["snapshot"]

    def replace_queue(multiplier: int, manually_declared: bool = False) -> dict:
        snapshot = build_queue_snapshot(patient_list, multiplier, manually_declared)
        with queue_lock:
            profile_id = profile_holder["profile_id"]
        apply_profile(snapshot["items"], snapshot["queue_length"], profile_id)
        apply_profile(suggestions.values(), snapshot["queue_length"], profile_id)
        snapshot["hospital_profile"] = profile_summary(profile_id)
        persist_items(snapshot["items"])
        with queue_lock:
            queue_holder["snapshot"] = snapshot
        return snapshot

    def switch_profile(profile_id: str) -> dict:
        profile_summary(profile_id)  # validates before mutating state
        with queue_lock:
            snapshot = queue_holder["snapshot"]
            profile_holder["profile_id"] = profile_id
            apply_profile(snapshot["items"], snapshot["queue_length"], profile_id)
            apply_profile(suggestions.values(), snapshot["queue_length"], profile_id)
            snapshot["hospital_profile"] = profile_summary(profile_id)
            return snapshot

    def current_suggestion(patient_id: str | None) -> dict | None:
        current = next((item for item in queue_snapshot()["items"] if item["patient_id"] == patient_id), None)
        return current or suggestions.get(patient_id)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send(200, page, "text/html; charset=utf-8")
            elif parsed.path == "/api/suggestions":
                self._json(200, list(suggestions.values()))
            elif parsed.path == "/api/queue":
                self._json(200, queue_snapshot())
            elif parsed.path == "/api/reasons":
                self._json(200, REASON_CODES)
            elif parsed.path == "/api/hospital-profiles":
                table = load_hospital_profiles()
                self._json(200, {
                    "active_profile_id": profile_holder["profile_id"], "disclaimer": table["disclaimer"],
                    "profiles": [{"profile_id": key, "display_name": value["display_name"],
                                  "facility_type": value["facility_type"]}
                                 for key, value in table["profiles"].items()],
                })
            elif parsed.path == "/api/audit":
                patient_id = parse_qs(parsed.query).get("patient_id", [None])[0]
                self._json(200, read_audit_events(audit_path, patient_id=patient_id))
            elif parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                patient_uid = query.get("patient_uid", [""])[0]
                current_id = query.get("current_encounter_id", [None])[0]
                if not patient_uid:
                    return self._json(400, {"error": "patient_uid is required"})
                self._json(200, {
                    "label": HISTORY_SCOPE_LABEL, "patient_uid": patient_uid,
                    "visits": previous_visits(history_runtime, patient_uid, current_id),
                    "complete_ehr_history": False,
                })
            elif parsed.path == "/api/kiosk/status":
                self._json(200, _kiosk_audio_status())
            elif parsed.path == "/api/fhir-export":
                encounter_id = parse_qs(parsed.query).get("encounter_id", [""])[0]
                try:
                    patient, encounter = encounter_with_patient(history_runtime, encounter_id)
                except ValueError as exc:
                    return self._json(404, {"error": str(exc)})
                bundle = build_fhir_shaped_bundle(patient, encounter)
                self._json(200, {"disclaimer": FHIR_SHAPED_DISCLAIMER, "bundle": bundle})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {
                "/api/overrides", "/api/routing-preview", "/api/surge/run", "/api/surge/reset",
                "/api/surge/manual", "/api/combat/acknowledge", "/api/hospital-profile",
                "/api/kiosk/text",
            }:
                return self._json(404, {"error": "not found"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 65536:
                    raise ValueError("request body must be between 1 and 65536 bytes")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                if path == "/api/surge/run":
                    return self._json(200, replace_queue(3))
                if path == "/api/surge/reset":
                    return self._json(200, replace_queue(1))
                if path == "/api/surge/manual":
                    active = payload.get("active")
                    if type(active) is not bool:
                        raise ValueError("active must be boolean")
                    current = queue_snapshot()
                    return self._json(200, replace_queue(current["load_multiplier"], active))
                if path == "/api/hospital-profile":
                    profile_id = payload.get("profile_id", "")
                    return self._json(200, switch_profile(profile_id))
                if path == "/api/kiosk/text":
                    transcript = payload.get("transcript", "")
                    if not isinstance(transcript, str) or not transcript.strip():
                        raise ValueError("transcript is required")
                    kiosk_result = process_kiosk_text(transcript)
                    kiosk_result["differential_matches"] = _kiosk_differential_preview(kiosk_result)
                    kiosk_result["experimental"] = True
                    return self._json(200, kiosk_result)
                suggestion = current_suggestion(payload.get("patient_id"))
                if not suggestion:
                    return self._json(404, {"error": "unknown patient_id"})
                if path == "/api/combat/acknowledge":
                    surge = queue_snapshot()["combat_mode"]
                    event = record_combat_acknowledgement(
                        audit_path, patient_id=suggestion["patient_id"],
                        clinician_id=payload.get("clinician_id", ""), ai_result=suggestion["ai_result"],
                        surge_state=surge, safety_badge=suggestion["safety_badge"],
                    )
                    return self._json(201, {"event": event, "patient": suggestion})
                if path == "/api/routing-preview":
                    result = suggestion["ai_result"]
                    return self._json(200, suggest_scheme_route(
                        suggestion.get("patient") or patients[suggestion["patient_id"]], result["point_estimate"],
                        clinician_confirmed=True, confidence_result=result,
                    ))
                upsert_current_encounter(
                    history_runtime, patient=suggestion["patient"], ai_result=suggestion["ai_result"],
                    safety_badge=suggestion["safety_badge"], encounter_id=suggestion["encounter_id"],
                    patient_uid=suggestion["patient_uid"],
                )
                event = record_clinician_override(
                    audit_path, patient_id=suggestion["patient_id"], clinician_id=payload.get("clinician_id", ""),
                    original_ai_result=suggestion["ai_result"], overridden_esi=payload.get("overridden_esi"),
                    reason_code=payload.get("reason_code", ""), reason_text=payload.get("reason_text", ""),
                )
                record_history_override(history_runtime, suggestion["encounter_id"], event)
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
