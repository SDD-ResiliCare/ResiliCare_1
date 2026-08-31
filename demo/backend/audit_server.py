"""Dependency-free local demo server for override capture and audit viewing."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlparse

PROJECT_ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from resilicare import (  # noqa: E402
    FHIR_SHAPED_DISCLAIMER,
    HISTORY_SCOPE_LABEL,
    REASON_CODES,
    assess_hospital_operations,
    build_fhir_shaped_bundle,
    combat_mode_state,
    compute_override_rates,
    confirmation_status,
    critical_safety_badge,
    encounter_with_patient,
    initialize_history_store,
    get_hospital_profile,
    load_simulated_patients,
    load_hospital_profiles,
    match_ambiguous_presentations,
    patient_uid_for_source,
    pending_confirmation,
    previous_visits,
    read_audit_events,
    record_combat_acknowledgement,
    record_clinician_override,
    record_clinician_confirmation,
    record_history_confirmation,
    record_history_override,
    replay_arrivals,
    redacted_compliance_events,
    score_with_confidence,
    suggest_scheme_route,
    upsert_current_encounter,
    log_provisional_result,
)
# EXPERIMENTAL Task 12 spike, not part of the clinical scoring path — see nlp_kiosk.py's module
# docstring and README's "Task 12" section. Imported explicitly (not via resilicare's __all__)
# so this stays visibly opt-in; the text pipeline it exposes needs no ASR/torch/spaCy deps.
from resilicare.nlp import process_kiosk_text, resolve_kiosk_chief_complaint  # noqa: E402


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
        "routing_assessment": suggest_scheme_route(patient, result["point_estimate"], clinician_confirmed=False, confidence_result=result),
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


def build_queue_snapshot(
    patients: list[dict], multiplier: int, manually_declared: bool = False, combat_threshold: int = 20,
) -> dict:
    replay = replay_arrivals(patients, multiplier=multiplier, deteriorate_first_patient=multiplier == 3)
    items = [build_patient_suggestion(entry["patient"], entry["current_esi"], entry) for entry in replay["queue"]]
    return {
        "scenario": replay["scenario"], "load_multiplier": replay["load_multiplier"],
        "arrival_window_minutes": replay["arrival_window_minutes"], "queue_length": len(items),
        "deterioration_demo": replay["deterioration_demo"],
        "combat_mode": combat_mode_state(len(items), manually_declared=manually_declared, threshold=combat_threshold),
        "queue_entries": replay["queue"],
        "items": items,
    }


def create_server(
    project_root: Path = PROJECT_ROOT,
    log_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
    history_path: Path | None = None,
    confirmation_timeout_seconds: int = 15 * 60,
) -> ThreadingHTTPServer:
    if type(confirmation_timeout_seconds) is not int or confirmation_timeout_seconds < 1:
        raise ValueError("confirmation_timeout_seconds must be a positive integer")
    dataset_path = project_root / "data" / "simulated_patients.json"
    patient_list = load_simulated_patients(dataset_path)
    suggestions = build_demo_suggestions(project_root)
    patients = {item["patient_id"]: item for item in patient_list}
    queue_lock, queue_holder = Lock(), {"snapshot": build_queue_snapshot(patient_list, 1)}
    profile_holder = {"profile_id": "urban_trauma_center"}
    confirmation_holder = {"records": {}, "unlocked_encounters": set(), "provisional_keys": set()}
    audit_path = log_path or project_root / "data" / "audit_log.jsonl"
    history_runtime = initialize_history_store(
        project_root / "data" / "resilicare_history_seed.json",
        history_path or project_root / "data" / "resilicare_history_runtime.json",
    )
    

    def apply_profile(items, queue_length: int, profile_id: str) -> None:
        for item in items:
            item["hospital_operations"] = assess_hospital_operations(
                item["patient"], item["ai_result"], profile_id, queue_length=queue_length,
            )

    def profile_summary(profile_id: str) -> dict:
        profile = get_hospital_profile(profile_id)
        return {"profile_id": profile_id, "display_name": profile["display_name"],
                "facility_type": profile["facility_type"], "combat_mode_queue_threshold": profile["combat_mode_queue_threshold"],
                "simulated": True}

    def persist_items(items) -> None:
        for item in items:
            upsert_current_encounter(
                history_runtime, patient=item["patient"], ai_result=item["ai_result"],
                safety_badge=item["safety_badge"], encounter_id=item["encounter_id"],
                patient_uid=item["patient_uid"],
            )

    def confirmation_for(item: dict, *, now: datetime | None = None) -> dict:
        encounter_id = item["encounter_id"]
        record = confirmation_holder["records"].get(encounter_id)
        if record is None:
            issued = now or datetime.now(timezone.utc)
            record = pending_confirmation(encounter_id=encounter_id, now=issued)
            record["expires_at"] = (issued + timedelta(seconds=confirmation_timeout_seconds)).isoformat()
            confirmation_holder["records"][encounter_id] = record
        current = confirmation_status(record, now=now)
        if current["status"] == "TIMED_OUT_SENIOR_REVIEW" and record.get("status") != "TIMED_OUT_SENIOR_REVIEW":
            log_provisional_result(audit_path, item["patient_id"], {
                **item["ai_result"], "confirmation_timeout": True, "confirmation": current,
            })
        confirmation_holder["records"][encounter_id] = current
        return current

    def attach_runtime_state(items: list[dict], queue_length: int, profile_id: str) -> None:
        for item in items:
            confirmation = confirmation_for(item)
            item["clinical_confirmation"] = confirmation
            item["routing_assessment"] = route_for(item, confirmation)

    def route_for(item: dict, confirmation: dict) -> dict:
        route = suggest_scheme_route(
            item["patient"], item["ai_result"]["point_estimate"],
            clinician_confirmed=bool(confirmation.get("routing_allowed")),
            confidence_result=item["ai_result"], operational_context=item.get("hospital_operations"),
        )
        route["clinical_confirmation"] = confirmation["status"]
        if confirmation["status"] == "TIMED_OUT_SENIOR_REVIEW":
            route.update({
                "status": "CLINICAL_ROUTING_BLOCKED",
                "message": "Confirmation timed out; retain the safety-capped ESI and obtain senior review before routing.",
                "blockers": list(dict.fromkeys(route["blockers"] + ["CONFIRMATION_TIMED_OUT"])),
            })
        return route

    def audit_provisional_items(items: list[dict]) -> None:
        for item in items:
            fingerprint = json.dumps({"encounter_id": item["encounter_id"], "ai_result": item["ai_result"]}, sort_keys=True)
            if fingerprint not in confirmation_holder["provisional_keys"]:
                log_provisional_result(audit_path, item["patient_id"], item["ai_result"])
                confirmation_holder["provisional_keys"].add(fingerprint)

    def refresh_snapshot(snapshot: dict, profile_id: str, manually_declared: bool = False) -> dict:
        threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
        snapshot["combat_mode"] = combat_mode_state(
            snapshot["queue_length"], manually_declared=manually_declared, threshold=threshold,
        )
        apply_profile(snapshot["items"], snapshot["queue_length"], profile_id)
        attach_runtime_state(snapshot["items"], snapshot["queue_length"], profile_id)
        snapshot["hospital_profile"] = profile_summary(profile_id)
        persist_items(snapshot["items"])
        audit_provisional_items(snapshot["items"])
        return snapshot

    def refresh_suggestions(profile_id: str, queue_length: int) -> None:
        apply_profile(list(suggestions.values()), queue_length, profile_id)
        attach_runtime_state(list(suggestions.values()), queue_length, profile_id)
        audit_provisional_items(list(suggestions.values()))

    refresh_snapshot(queue_holder["snapshot"], profile_holder["profile_id"])
    refresh_suggestions(profile_holder["profile_id"], queue_holder["snapshot"]["queue_length"])

    def queue_snapshot() -> dict:
        with queue_lock:
            return deepcopy(queue_holder["snapshot"])

    def replace_queue(multiplier: int, manually_declared: bool = False) -> dict:
        with queue_lock:
            profile_id = profile_holder["profile_id"]
            confirmation_holder["records"].clear()
            confirmation_holder["unlocked_encounters"].clear()
        threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
        snapshot = build_queue_snapshot(patient_list, multiplier, manually_declared, threshold)
        refresh_snapshot(snapshot, profile_id, manually_declared)
        refresh_suggestions(profile_id, snapshot["queue_length"])
        with queue_lock:
            queue_holder["snapshot"] = snapshot
        return render_queue_snapshot(snapshot)

    def switch_profile(profile_id: str) -> dict:
        profile_summary(profile_id)  # validates before mutating state
        with queue_lock:
            snapshot = queue_holder["snapshot"]
            profile_holder["profile_id"] = profile_id
            refresh_snapshot(snapshot, profile_id, snapshot["combat_mode"]["trigger"] == "MANUAL")
            refresh_suggestions(profile_id, snapshot["queue_length"])
            return render_queue_snapshot(snapshot)

    def current_suggestion(patient_id: str | None) -> dict | None:
        current = next((item for item in queue_snapshot()["items"] if item["patient_id"] == patient_id), None)
        return current or deepcopy(suggestions.get(patient_id))

    def compact_combat_item(item: dict) -> dict:
        return {
            "patient_id": item["patient_id"], "encounter_id": item["encounter_id"],
            "safety_badge": item["safety_badge"],
            "explanation_clause": (item["ai_result"].get("explanation_lines") or [item["safety_badge"]["reason"]])[0],
            "combat_mode_locked": True,
        }

    def render_queue_snapshot(snapshot: dict) -> dict:
        rendered = deepcopy(snapshot)
        for item in rendered["items"]:
            confirmation = confirmation_for(item)
            item["clinical_confirmation"] = confirmation
            item["routing_assessment"] = route_for(item, confirmation)
        if rendered["combat_mode"]["active"]:
            rendered["items"] = [
                item if item["encounter_id"] in confirmation_holder["unlocked_encounters"] else compact_combat_item(item)
                for item in rendered["items"]
            ]
        rendered.pop("queue_entries", None)
        return rendered

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            routes = {
                "/": self.serve_api_docs,
                
                
                "/api/hospital/suggestions": self.get_suggestions,
                "/api/hospital/queue": self.get_queue,
                "/api/hospital/reasons": self.get_reasons,
                "/api/hospital/profiles": self.get_hospital_profiles,
                "/api/hospital/audit": self.get_audit,
                "/api/hospital/audit/compliance-export": self.get_compliance_export,
                "/api/patient/history": self.get_history,
                "/api/patient/kiosk-status": self.get_kiosk_status,
                "/api/hospital/fhir-export": self.get_fhir_export,
                "/api/hospital/override-rates": self.get_override_rates,
                "/api/hospital/surge/evidence": self.get_surge_evidence,
                "/api/hospital/profile-comparison": self.get_profile_comparison,
            }
            handler = routes.get(parsed.path)
            if handler:
                handler(parsed)
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            parsed = urlparse(self.path)
            routes = {
                "/api/hospital/surge/run": self.post_surge_run,
                "/api/hospital/surge/reset": self.post_surge_reset,
                "/api/hospital/surge/manual": self.post_surge_manual,
                "/api/hospital/profile": self.post_hospital_profile,
                "/api/hospital/confirmations": self.post_confirmation,
                "/api/hospital/queue/vitals": self.post_queue_vitals,
                "/api/patient/kiosk-text": self.post_kiosk_text,
                "/api/hospital/combat-acknowledge": self.post_combat_acknowledge,
                "/api/patient/routing-preview": self.post_routing_preview,
                "/api/hospital/overrides": self.post_overrides,
            }
            handler = routes.get(parsed.path)
            if not handler:
                return self._json(404, {"error": "not found"})
            
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if size <= 0 or size > 65536:
                    raise ValueError("request body must be between 1 and 65536 bytes")
                payload = json.loads(self.rfile.read(size))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                handler(payload)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def serve_api_docs(self, parsed):
            self._json(200, {
                "message": "ResiliCare API Server is running.",
                "namespaces": {
                    "hospital_facing": {
                        "GET": ["/api/hospital/suggestions", "/api/hospital/queue", "/api/hospital/reasons", "/api/hospital/profiles", "/api/hospital/audit", "/api/hospital/audit/compliance-export", "/api/hospital/fhir-export", "/api/hospital/override-rates", "/api/hospital/surge/evidence", "/api/hospital/profile-comparison?patient_id=X"],
                        "POST": ["/api/hospital/surge/run", "/api/hospital/surge/reset", "/api/hospital/surge/manual", "/api/hospital/profile", "/api/hospital/confirmations", "/api/hospital/queue/vitals", "/api/hospital/combat-acknowledge", "/api/hospital/overrides"]
                    },
                    "patient_facing": {
                        "GET": ["/api/patient/history", "/api/patient/kiosk-status"],
                        "POST": ["/api/patient/kiosk-text", "/api/patient/routing-preview"]
                    }
                }
            })
            
        def get_suggestions(self, parsed):
            rendered = deepcopy(list(suggestions.values()))
            for item in rendered:
                confirmation = confirmation_for(item)
                item["clinical_confirmation"] = confirmation
                item["routing_assessment"] = route_for(item, confirmation)
            self._json(200, rendered)
            
        def get_queue(self, parsed):
            self._json(200, render_queue_snapshot(queue_snapshot()))
            
        def get_reasons(self, parsed):
            self._json(200, REASON_CODES)
            
        def get_hospital_profiles(self, parsed):
            table = load_hospital_profiles()
            self._json(200, {
                "active_profile_id": profile_holder["profile_id"], "disclaimer": table["disclaimer"],
                "profiles": [{"profile_id": key, "display_name": value["display_name"],
                              "facility_type": value["facility_type"]}
                             for key, value in table["profiles"].items()],
            })
            
        def get_audit(self, parsed):
            patient_id = parse_qs(parsed.query).get("patient_id", [None])[0]
            self._json(200, read_audit_events(audit_path, patient_id=patient_id))

        def get_compliance_export(self, parsed):
            self._json(200, redacted_compliance_events(audit_path))
            
        def get_history(self, parsed):
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
            
        def get_kiosk_status(self, parsed):
            self._json(200, _kiosk_audio_status())
            
        
        def get_override_rates(self, parsed):
            self._json(200, compute_override_rates(audit_path))

        def get_surge_evidence(self, parsed):
            profile_id = profile_holder["profile_id"]
            threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
            quiet = build_queue_snapshot(patient_list, 1, combat_threshold=threshold)
            surge = build_queue_snapshot(patient_list, 3, combat_threshold=threshold)

            def evidence(snapshot):
                return {
                    "scenario": snapshot["scenario"], "queue_length": snapshot["queue_length"],
                    "combat_mode": snapshot["combat_mode"], "queue_order": [
                        {"patient_id": item["patient_id"], "source_patient_id": item["source_patient_id"],
                         "queue_rank": item["queue"]["queue_rank"], "esi": item["ai_result"]["point_estimate"]}
                        for item in snapshot["items"]
                    ],
                }

            self._json(200, {"hospital_profile": profile_summary(profile_id), "quiet_before": evidence(quiet), "surge_after": evidence(surge)})

        def get_profile_comparison(self, parsed):
            patient_id = parse_qs(parsed.query).get("patient_id", [None])[0]
            suggestion = current_suggestion(patient_id)
            if not suggestion:
                return self._json(404, {"error": "unknown patient_id"})
            queue_length = queue_snapshot()["queue_length"]
            comparison = []
            for profile_id in sorted(load_hospital_profiles()["profiles"]):
                operations = assess_hospital_operations(
                    suggestion["patient"], suggestion["ai_result"], profile_id, queue_length=queue_length,
                )
                comparison.append({
                    "profile": profile_summary(profile_id), "esi_unchanged": suggestion["ai_result"]["point_estimate"],
                    "operations": operations,
                })
            self._json(200, {"patient_id": suggestion["patient_id"], "encounter_id": suggestion["encounter_id"], "comparison": comparison})

        def get_fhir_export(self, parsed):
            encounter_id = parse_qs(parsed.query).get("encounter_id", [""])[0]
            try:
                patient, encounter = encounter_with_patient(history_runtime, encounter_id)
            except ValueError as exc:
                return self._json(404, {"error": str(exc)})
            bundle = build_fhir_shaped_bundle(patient, encounter)
            self._json(200, {"disclaimer": FHIR_SHAPED_DISCLAIMER, "bundle": bundle})

        def post_surge_run(self, payload):
            self._json(200, replace_queue(3))
            
        def post_surge_reset(self, payload):
            self._json(200, replace_queue(1))
            
        def post_surge_manual(self, payload):
            active = payload.get("active")
            if type(active) is not bool:
                raise ValueError("active must be boolean")
            current = queue_snapshot()
            self._json(200, replace_queue(current["load_multiplier"], active))
            
        def post_hospital_profile(self, payload):
            profile_id = payload.get("profile_id", "")
            self._json(200, switch_profile(profile_id))

        def post_confirmation(self, payload):
            suggestion = current_suggestion(payload.get("patient_id"))
            if not suggestion:
                return self._json(404, {"error": "unknown patient_id"})
            confirmation = confirmation_for(suggestion)
            role = payload.get("clinician_role", "")
            if confirmation["status"] == "TIMED_OUT_SENIOR_REVIEW" and str(role).upper() != "MD":
                raise ValueError("a timed-out confirmation requires MD senior review")
            event = record_clinician_confirmation(
                audit_path, patient_id=suggestion["patient_id"], encounter_id=suggestion["encounter_id"],
                clinician_id=payload.get("clinician_id", ""), clinician_role=role, ai_result=suggestion["ai_result"],
            )
            confirmation_holder["records"][suggestion["encounter_id"]] = {
                "encounter_id": suggestion["encounter_id"], "status": "CONFIRMED", "routing_allowed": True,
                "confirmed_at": event["timestamp"], "clinician_id": event["clinician_id"], "clinician_role": event["clinician_role"],
                "confirmed_esi": event["confirmed_esi"],
            }
            upsert_current_encounter(
                history_runtime, patient=suggestion["patient"], ai_result=suggestion["ai_result"],
                safety_badge=suggestion["safety_badge"], encounter_id=suggestion["encounter_id"], patient_uid=suggestion["patient_uid"],
            )
            record_history_confirmation(history_runtime, suggestion["encounter_id"], event)
            with queue_lock:
                snapshot = queue_holder["snapshot"]
                refresh_snapshot(snapshot, profile_holder["profile_id"], snapshot["combat_mode"]["trigger"] == "MANUAL")
                refresh_suggestions(profile_holder["profile_id"], snapshot["queue_length"])
            confirmed = confirmation_holder["records"][suggestion["encounter_id"]]
            self._json(201, {"event": event, "clinical_confirmation": confirmed, "routing_assessment": route_for(suggestion, confirmed)})

        def post_queue_vitals(self, payload):
            patient_id, vitals = payload.get("patient_id"), payload.get("vitals")
            if not isinstance(patient_id, str) or not isinstance(vitals, dict):
                raise ValueError("patient_id and vitals object are required")
            snapshot = queue_snapshot()
            entry = next((item for item in snapshot["queue_entries"] if item["patient_id"] == patient_id), None)
            if not entry:
                return self._json(404, {"error": "unknown queue patient_id"})
            observed_at = payload.get("observed_at")
            max_queue_time = max(datetime.fromisoformat(item["last_assessed_at"]) for item in snapshot["queue_entries"])
            if observed_at is None or datetime.fromisoformat(observed_at) < max_queue_time:
                observed_at = (max_queue_time + timedelta(minutes=1)).isoformat()
            from resilicare.queue.waiting_room import tick_waiting_room

            snapshot["queue_entries"] = tick_waiting_room(
                snapshot["queue_entries"], observed_at, vital_updates={patient_id: vitals}, log_path=audit_path,
            )
            snapshot["items"] = [
                build_patient_suggestion(entry["patient"], entry["current_esi"], entry)
                for entry in snapshot["queue_entries"]
            ]
            confirmation_holder["records"].pop(patient_id, None)
            confirmation_holder["unlocked_encounters"].discard(patient_id)
            profile_id = profile_holder["profile_id"]
            refresh_snapshot(snapshot, profile_id, snapshot["combat_mode"]["trigger"] == "MANUAL")
            refresh_suggestions(profile_id, snapshot["queue_length"])
            with queue_lock:
                queue_holder["snapshot"] = snapshot
            self._json(200, render_queue_snapshot(snapshot))
            
        def post_kiosk_text(self, payload):
            transcript = payload.get("transcript", "")
            if not isinstance(transcript, str) or not transcript.strip():
                raise ValueError("transcript is required")
            kiosk_result = process_kiosk_text(transcript)
            kiosk_result["differential_matches"] = _kiosk_differential_preview(kiosk_result)
            kiosk_result["experimental"] = True
            self._json(200, kiosk_result)
            
        def post_combat_acknowledge(self, payload):
            suggestion = current_suggestion(payload.get("patient_id"))
            if not suggestion:
                return self._json(404, {"error": "unknown patient_id"})
            surge = queue_snapshot()["combat_mode"]
            event = record_combat_acknowledgement(
                audit_path, patient_id=suggestion["patient_id"],
                clinician_id=payload.get("clinician_id", ""), clinician_role=payload.get("clinician_role", ""), ai_result=suggestion["ai_result"],
                surge_state=surge, safety_badge=suggestion["safety_badge"],
            )
            confirmation_holder["unlocked_encounters"].add(suggestion["encounter_id"])
            self._json(201, {"event": event, "patient": suggestion})
            
        def post_routing_preview(self, payload):
            suggestion = current_suggestion(payload.get("patient_id"))
            if not suggestion:
                return self._json(404, {"error": "unknown patient_id"})
            confirmation = confirmation_for(suggestion)
            self._json(200, route_for(suggestion, confirmation))
            
        def post_overrides(self, payload):
            suggestion = current_suggestion(payload.get("patient_id"))
            if not suggestion:
                return self._json(404, {"error": "unknown patient_id"})
            upsert_current_encounter(
                history_runtime, patient=suggestion["patient"], ai_result=suggestion["ai_result"],
                safety_badge=suggestion["safety_badge"], encounter_id=suggestion["encounter_id"],
                patient_uid=suggestion["patient_uid"],
            )
            event = record_clinician_override(
                audit_path, patient_id=suggestion["patient_id"], clinician_id=payload.get("clinician_id", ""), clinician_role=payload.get("clinician_role", ""),
                original_ai_result=suggestion["ai_result"], overridden_esi=payload.get("overridden_esi"),
                reason_code=payload.get("reason_code", ""), reason_text=payload.get("reason_text", ""),
            )
            record_history_override(history_runtime, suggestion["encounter_id"], event)
            confirmation_holder["records"][suggestion["encounter_id"]] = {
                "encounter_id": suggestion["encounter_id"], "status": "CLINICIAN_OVERRIDE", "routing_allowed": False,
                "override_event_id": event["event_id"], "clinician_id": event["clinician_id"], "clinician_role": event["clinician_role"],
            }
            self._json(201, event)

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
