"""Data shaping functions for the API."""

import json
from pathlib import Path

from src.adapters.clinical_routing import suggest_scheme_route
from src.core.confidence_scoring import score_with_confidence
from src.data.history_store import patient_uid_for_source
from src.workflows.combat_mode import combat_mode_state, critical_safety_badge
from src.workflows.queue_surge import replay_arrivals


def build_patient_suggestion(patient: dict, proposed_esi: int | None = None, queue_entry: dict | None = None) -> dict:
    result = score_with_confidence(patient, proposed_esi or int(patient["reference_esi"]))
    source_patient_id = patient.get("source_patient_id", patient["patient_id"])
    item = {
        "patient_id": patient["patient_id"], "encounter_id": patient["patient_id"],
        "source_patient_id": source_patient_id, "patient_uid": patient_uid_for_source(str(source_patient_id)),
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
