"""Patient-facing routes."""

import importlib.util
from datetime import datetime

from src.data.history_store import HISTORY_SCOPE_LABEL, previous_visits
from src.core.clinical_differentials import match_ambiguous_presentations
from src.api.state import ServerState

# Experimental nlp spike imports
from src.nlp import process_kiosk_text, resolve_kiosk_chief_complaint


def _kiosk_differential_preview(kiosk_result: dict) -> list[dict]:
    complaint = resolve_kiosk_chief_complaint(kiosk_result)
    if not complaint:
        return []
    return match_ambiguous_presentations({"chief_complaint": complaint})


def _kiosk_audio_status() -> dict:
    missing = [name for name in ("torch", "librosa", "transformers", "spacy")
               if importlib.util.find_spec(name) is None]
    return {
        "audio_pipeline_available": not missing, "missing_dependencies": missing,
        "note": "Task 12 audio intake is an experimental spike, not a demo-ready feature. "
                "Use manual transcript entry below regardless of this status.",
    }


def get_history(state: ServerState, query: dict) -> tuple[int, dict | list]:
    patient_uid = query.get("patient_uid", [""])[0]
    current_id = query.get("current_encounter_id", [None])[0]
    if not patient_uid:
        return 400, {"error": "patient_uid is required"}
    return 200, {
        "label": HISTORY_SCOPE_LABEL, "patient_uid": patient_uid,
        "visits": previous_visits(state.history_runtime, patient_uid, current_id),
        "complete_ehr_history": False,
    }


def get_kiosk_status(state: ServerState, query: dict) -> tuple[int, dict | list]:
    return 200, _kiosk_audio_status()


def post_kiosk_text(state: ServerState, payload: dict) -> tuple[int, dict | list]:
    transcript = payload.get("transcript", "")
    if not isinstance(transcript, str) or not transcript.strip():
        return 400, {"error": "transcript is required"}
    kiosk_result = process_kiosk_text(transcript)
    kiosk_result["differential_matches"] = _kiosk_differential_preview(kiosk_result)
    kiosk_result["experimental"] = True
    return 200, kiosk_result


def post_routing_preview(state: ServerState, payload: dict) -> tuple[int, dict | list]:
    suggestion = state.current_suggestion(payload.get("patient_id"))
    if not suggestion:
        return 404, {"error": "unknown patient_id"}
    confirmation = state.confirmation_for(suggestion)
    return 200, state.route_for(suggestion, confirmation)
