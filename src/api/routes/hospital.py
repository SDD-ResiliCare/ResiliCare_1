"""Hospital-facing routes."""

import copy
from datetime import datetime, timedelta

from src.api.state import ServerState
from src.data.audit_log import REASON_CODES, compute_override_rates, read_audit_events, record_clinician_override, redacted_compliance_events
from src.workflows.combat_mode import record_combat_acknowledgement
from src.data.clinical_confirmation import record_clinician_confirmation
from src.adapters.hospital_config import load_hospital_profiles, assess_hospital_operations, get_hospital_profile
from src.adapters.fhir_exporter import build_fhir_shaped_bundle, FHIR_SHAPED_DISCLAIMER
from src.api.models import build_queue_snapshot, build_patient_suggestion
from src.data.history_store import encounter_with_patient, record_history_override, record_history_confirmation, upsert_current_encounter


def get_suggestions(state: ServerState, query: dict) -> tuple[int, dict]:
    rendered = copy.deepcopy(list(state.suggestions.values()))
    for item in rendered:
        confirmation = state.confirmation_for(item)
        item["clinical_confirmation"] = confirmation
        item["routing_assessment"] = state.route_for(item, confirmation)
    return 200, rendered


def get_queue(state: ServerState, query: dict) -> tuple[int, dict]:
    return 200, state.render_queue_snapshot(state.queue_snapshot())


def get_reasons(state: ServerState, query: dict) -> tuple[int, dict]:
    return 200, REASON_CODES


def get_hospital_profiles(state: ServerState, query: dict) -> tuple[int, dict]:
    table = load_hospital_profiles()
    return 200, {
        "active_profile_id": state.profile_holder["profile_id"], "disclaimer": table["disclaimer"],
        "profiles": [{"profile_id": key, "display_name": value["display_name"],
                      "facility_type": value["facility_type"]}
                     for key, value in table["profiles"].items()],
    }


def get_audit(state: ServerState, query: dict) -> tuple[int, dict]:
    patient_id = query.get("patient_id", [None])[0]
    return 200, read_audit_events(state.log_path, patient_id=patient_id)


def get_compliance_export(state: ServerState, query: dict) -> tuple[int, dict]:
    return 200, redacted_compliance_events(state.log_path)


def get_fhir_export(state: ServerState, query: dict) -> tuple[int, dict]:
    encounter_id = query.get("encounter_id", [""])[0]
    try:
        patient, encounter = encounter_with_patient(state.history_runtime, encounter_id)
    except ValueError as exc:
        return 404, {"error": str(exc)}
    bundle = build_fhir_shaped_bundle(patient, encounter)
    return 200, {"disclaimer": FHIR_SHAPED_DISCLAIMER, "bundle": bundle}


def get_override_rates(state: ServerState, query: dict) -> tuple[int, dict]:
    return 200, compute_override_rates(state.log_path)


def get_surge_evidence(state: ServerState, query: dict) -> tuple[int, dict]:
    profile_id = state.profile_holder["profile_id"]
    threshold = get_hospital_profile(profile_id)["combat_mode_queue_threshold"]
    quiet = build_queue_snapshot(state.patient_list, 1, combat_threshold=threshold)
    surge = build_queue_snapshot(state.patient_list, 3, combat_threshold=threshold)

    def evidence(snapshot):
        return {
            "scenario": snapshot["scenario"], "queue_length": snapshot["queue_length"],
            "combat_mode": snapshot["combat_mode"], "queue_order": [
                {"patient_id": item["patient_id"], "source_patient_id": item["source_patient_id"],
                 "queue_rank": item["queue"]["queue_rank"], "esi": item["ai_result"]["point_estimate"]}
                for item in snapshot["items"]
            ],
        }

    return 200, {"hospital_profile": state.profile_summary(profile_id), "quiet_before": evidence(quiet), "surge_after": evidence(surge)}


def get_profile_comparison(state: ServerState, query: dict) -> tuple[int, dict]:
    patient_id = query.get("patient_id", [None])[0]
    suggestion = state.current_suggestion(patient_id)
    if not suggestion:
        return 404, {"error": "unknown patient_id"}
    queue_length = state.queue_snapshot()["queue_length"]
    comparison = []
    for profile_id in sorted(load_hospital_profiles()["profiles"]):
        operations = assess_hospital_operations(
            suggestion["patient"], suggestion["ai_result"], profile_id, queue_length=queue_length,
        )
        comparison.append({
            "profile": state.profile_summary(profile_id), "esi_unchanged": suggestion["ai_result"]["point_estimate"],
            "operations": operations,
        })
    return 200, {"patient_id": suggestion["patient_id"], "encounter_id": suggestion["encounter_id"], "comparison": comparison}


def post_surge_run(state: ServerState, payload: dict) -> tuple[int, dict]:
    return 200, state.replace_queue(3)


def post_surge_reset(state: ServerState, payload: dict) -> tuple[int, dict]:
    return 200, state.replace_queue(1)


def post_surge_manual(state: ServerState, payload: dict) -> tuple[int, dict]:
    active = payload.get("active")
    if type(active) is not bool:
        return 400, {"error": "active must be boolean"}
    current = state.queue_snapshot()
    return 200, state.replace_queue(current["load_multiplier"], active)


def post_hospital_profile(state: ServerState, payload: dict) -> tuple[int, dict]:
    profile_id = payload.get("profile_id", "")
    return 200, state.switch_profile(profile_id)


def post_confirmation(state: ServerState, payload: dict) -> tuple[int, dict]:
    suggestion = state.current_suggestion(payload.get("patient_id"))
    if not suggestion:
        return 404, {"error": "unknown patient_id"}
    confirmation = state.confirmation_for(suggestion)
    role = payload.get("clinician_role", "")
    if confirmation["status"] == "TIMED_OUT_SENIOR_REVIEW" and str(role).upper() != "MD":
        return 400, {"error": "a timed-out confirmation requires MD senior review"}
    event = record_clinician_confirmation(
        state.log_path, patient_id=suggestion["patient_id"], encounter_id=suggestion["encounter_id"],
        clinician_id=payload.get("clinician_id", ""), clinician_role=role, ai_result=suggestion["ai_result"],
    )
    state.confirmation_holder["records"][suggestion["encounter_id"]] = {
        "encounter_id": suggestion["encounter_id"], "status": "CONFIRMED", "routing_allowed": True,
        "confirmed_at": event["timestamp"], "clinician_id": event["clinician_id"], "clinician_role": event["clinician_role"],
        "confirmed_esi": event["confirmed_esi"],
    }
    upsert_current_encounter(
        state.history_runtime, patient=suggestion["patient"], ai_result=suggestion["ai_result"],
        safety_badge=suggestion["safety_badge"], encounter_id=suggestion["encounter_id"], patient_uid=suggestion["patient_uid"],
    )
    record_history_confirmation(state.history_runtime, suggestion["encounter_id"], event)
    with state.queue_lock:
        snapshot = state.queue_holder["snapshot"]
        state.refresh_snapshot(snapshot, state.profile_holder["profile_id"], snapshot["combat_mode"]["trigger"] == "MANUAL")
        state.refresh_suggestions(state.profile_holder["profile_id"], snapshot["queue_length"])
    confirmed = state.confirmation_holder["records"][suggestion["encounter_id"]]
    return 201, {"event": event, "clinical_confirmation": confirmed, "routing_assessment": state.route_for(suggestion, confirmed)}


def post_queue_vitals(state: ServerState, payload: dict) -> tuple[int, dict]:
    patient_id, vitals = payload.get("patient_id"), payload.get("vitals")
    if not isinstance(patient_id, str) or not isinstance(vitals, dict):
        return 400, {"error": "patient_id and vitals object are required"}
    snapshot = state.queue_snapshot()
    entry = next((item for item in snapshot["queue_entries"] if item["patient_id"] == patient_id), None)
    if not entry:
        return 404, {"error": "unknown queue patient_id"}
    observed_at = payload.get("observed_at")
    max_queue_time = max(datetime.fromisoformat(item["last_assessed_at"]) for item in snapshot["queue_entries"])
    if observed_at is None or datetime.fromisoformat(observed_at) < max_queue_time:
        observed_at = (max_queue_time + timedelta(minutes=1)).isoformat()
    from src.workflows.waiting_room import tick_waiting_room

    snapshot["queue_entries"] = tick_waiting_room(
        snapshot["queue_entries"], observed_at, vital_updates={patient_id: vitals}, log_path=state.log_path,
    )
    snapshot["items"] = [
        build_patient_suggestion(entry["patient"], entry["current_esi"], entry)
        for entry in snapshot["queue_entries"]
    ]
    state.confirmation_holder["records"].pop(patient_id, None)
    state.confirmation_holder["unlocked_encounters"].discard(patient_id)
    profile_id = state.profile_holder["profile_id"]
    state.refresh_snapshot(snapshot, profile_id, snapshot["combat_mode"]["trigger"] == "MANUAL")
    state.refresh_suggestions(profile_id, snapshot["queue_length"])
    with state.queue_lock:
        state.queue_holder["snapshot"] = snapshot
    return 200, state.render_queue_snapshot(snapshot)


def post_combat_acknowledge(state: ServerState, payload: dict) -> tuple[int, dict]:
    suggestion = state.current_suggestion(payload.get("patient_id"))
    if not suggestion:
        return 404, {"error": "unknown patient_id"}
    surge = state.queue_snapshot()["combat_mode"]
    event = record_combat_acknowledgement(
        state.log_path, patient_id=suggestion["patient_id"],
        clinician_id=payload.get("clinician_id", ""), clinician_role=payload.get("clinician_role", ""), ai_result=suggestion["ai_result"],
        surge_state=surge, safety_badge=suggestion["safety_badge"],
    )
    state.confirmation_holder["unlocked_encounters"].add(suggestion["encounter_id"])
    return 201, {"event": event, "patient": suggestion}


def post_overrides(state: ServerState, payload: dict) -> tuple[int, dict]:
    suggestion = state.current_suggestion(payload.get("patient_id"))
    if not suggestion:
        return 404, {"error": "unknown patient_id"}
    upsert_current_encounter(
        state.history_runtime, patient=suggestion["patient"], ai_result=suggestion["ai_result"],
        safety_badge=suggestion["safety_badge"], encounter_id=suggestion["encounter_id"],
        patient_uid=suggestion["patient_uid"],
    )
    event = record_clinician_override(
        state.log_path, patient_id=suggestion["patient_id"], clinician_id=payload.get("clinician_id", ""), clinician_role=payload.get("clinician_role", ""),
        original_ai_result=suggestion["ai_result"], overridden_esi=payload.get("overridden_esi"),
        reason_code=payload.get("reason_code", ""), reason_text=payload.get("reason_text", ""),
    )
    record_history_override(state.history_runtime, suggestion["encounter_id"], event)
    state.confirmation_holder["records"][suggestion["encounter_id"]] = {
        "encounter_id": suggestion["encounter_id"], "status": "CLINICIAN_OVERRIDE", "routing_allowed": False,
        "override_event_id": event["event_id"], "clinician_id": event["clinician_id"], "clinician_role": event["clinician_role"],
    }
    return 201, event
