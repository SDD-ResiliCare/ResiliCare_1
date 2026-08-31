"""Deterministic safety overrides for the ResiliCare triage prototype."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Iterable
from uuid import uuid4

from resilicare.engine.differentials import match_ambiguous_presentations
from resilicare.engine.vitals import prepare_patient_vitals

VITAL_FIELDS = ("hr_bpm", "rr_bpm", "spo2_pct", "sbp_mmhg", "dbp_mmhg", "temp_c")
VALID_ESI = range(1, 6)
_AUDIT_LOCK = Lock()


def evaluate_safety_rules(patient: dict[str, Any], prediction_range: Iterable[int] | None = None) -> dict[str, Any]:
    """Evaluate every safety rule and return the most urgent matched ceiling."""
    if patient.get("age_years") is not None and "vital_deviations" not in patient:
        patient = prepare_patient_vitals(patient)
    matches: list[tuple[str, int, str]] = []
    missing_or_conflicting: list[str] = []

    def add(rule_id: str, level: int, rationale: str) -> None:
        matches.append((rule_id, level, rationale))

    ambiguous_presentations = match_ambiguous_presentations(patient)

    if patient.get("immediate_lifesaving_intervention") is True:
        add("IMMEDIATE.LIFE_SAVING_INTERVENTION", 1, "Immediate life-saving intervention is likely.")
    if patient.get("high_risk_presentation") is True:
        add("HIGH_RISK.TIME_SENSITIVE_PRESENTATION", 2, "Presentation is marked high-risk or time-sensitive.")
    if patient.get("ambiguity_flag") is True:
        add("REVIEW.AMBIGUOUS_PRESENTATION", 3, "Symptoms have competing plausible interpretations.")
    for pathway in ambiguous_presentations:
        add(
            f"REVIEW.DIFFERENTIAL.{pathway['pathway_id']}",
            pathway["maximum_allowed_esi"],
            f"{pathway['label']} matched a mandatory safety-workup pathway.",
        )

    deviations = patient.get("vital_deviations") or {}
    missing_vitals = (
        [name for name, item in deviations.items() if item["status"] == "MISSING"]
        + (["dbp_mmhg"] if deviations and patient.get("dbp_mmhg") is None else [])
        if deviations else [name for name in VITAL_FIELDS if patient.get(name) is None]
    )
    if missing_vitals:
        missing_or_conflicting.append("Missing vitals: " + ", ".join(missing_vitals))
        add("REVIEW.MISSING_VITALS", 3, "One or more required intake vitals are missing.")
    if patient.get("relevant_history_missing") is True:
        missing_or_conflicting.append("Relevant history is missing")
        add("REVIEW.RELEVANT_HISTORY_MISSING", 3, "Relevant history needed for safe triage is unavailable.")
    if patient.get("borderline_vitals") is True:
        outside = [name for name, item in deviations.items() if item["status"] in {"LOW", "HIGH"}]
        detail = f" ({', '.join(outside)} outside the age-adjusted band)" if outside else ""
        add("REVIEW.BORDERLINE_VITALS", 3, "Vitals require clinician interpretation" + detail + ".")
    if patient.get("worsening_vitals") is True:
        add("REVIEW.WORSENING_VITALS", 3, "Repeat vitals are worsening.")

    conflicts = patient.get("conflicting_information") or []
    if isinstance(conflicts, str):
        conflicts = [conflicts]
    if conflicts:
        missing_or_conflicting.extend(f"Conflict: {item}" for item in conflicts)
        add("REVIEW.CONFLICTING_INFORMATION", 3, "Available information contains a clinically relevant conflict.")

    uncertainty = tuple(prediction_range or patient.get("prediction_range") or ())
    if uncertainty and (len(uncertainty) != 2 or any(level not in VALID_ESI for level in uncertainty)):
        raise ValueError("prediction_range must contain two ESI levels from 1 to 5")
    if uncertainty in {(2, 3), (3, 2)}:
        add("REVIEW.UNCERTAINTY_2_3", 3, "Prediction spans ESI 2 and 3.")
    if uncertainty in {(3, 4), (4, 3)}:
        add("REVIEW.UNCERTAINTY_3_4", 3, "Prediction spans ESI 3 and 4.")

    level = min((match[1] for match in matches), default=None)
    return {
        "status": "HARD_OVERRIDE" if level else "NO_HARD_OVERRIDE",
        "provisional_esi": level,
        "maximum_allowed_esi": level,
        "uncertainty_range": sorted(uncertainty) if uncertainty else None,
        "matched_rule_ids": [match[0] for match in matches],
        "rationale": [match[2] for match in matches],
        "review_priority": {1: "IMMEDIATE", 2: "HIGH", 3: "MANDATORY"}.get(level, "STANDARD"),
        "missing_or_conflicting_information": list(dict.fromkeys(missing_or_conflicting)),
        "requires_clinician_confirmation": True,
        "highlight_alert": level in {1, 2, 3},
        "regular_scorer_action": {1: "SKIP", 2: "RUN_WITH_CEILING", 3: "RUN_WITH_CEILING"}.get(level, "RUN"),
        "age_adjusted_vitals": patient.get("age_adjusted_vitals"),
        "ambiguous_presentations": ambiguous_presentations,
    }


def apply_safety_ceiling(regular_esi: int, safety_result: dict[str, Any]) -> int:
    """Combine a regular score with the safety ceiling without ever downgrading acuity."""
    if regular_esi not in VALID_ESI:
        raise ValueError("regular_esi must be between 1 and 5")
    ceiling = safety_result.get("maximum_allowed_esi")
    return min(regular_esi, ceiling) if ceiling else regular_esi


def log_provisional_result(log_path: str | Path, patient_id: str, result: dict[str, Any]) -> dict[str, Any]:
    return append_audit_event(log_path, "provisional_safety_result", patient_id, {"result": result})


def log_clinician_decision(
    log_path: str | Path,
    patient_id: str,
    result: dict[str, Any],
    clinician_id: str,
    decision: str,
    displayed_esi: int,
    final_esi: int,
    reason: str = "",
) -> dict[str, Any]:
    """Append a clinician accept/override event; overrides require a reason."""
    if decision not in {"accept", "override"} or displayed_esi not in VALID_ESI or final_esi not in VALID_ESI:
        raise ValueError("decision must be accept/override and ESI values must be between 1 and 5")
    if decision == "accept" and final_esi != displayed_esi:
        raise ValueError("an accepted score must equal the displayed score")
    if decision == "override" and not reason.strip():
        raise ValueError("an override requires a reason")
    direction = "no_change" if final_esi == displayed_esi else ("escalation" if final_esi < displayed_esi else "de_escalation")
    displayed_rules = result.get("explanation_rule_ids")
    if displayed_rules is None:
        displayed_rules = result.get("matched_rule_ids", [])[:2]

    details = {
        "clinician_id": clinician_id, "decision": decision, "displayed_esi": displayed_esi,
        "final_esi": final_esi, "override_direction": direction, "reason": reason.strip() or None,
        "provisional_esi": result.get("provisional_esi"), "matched_rule_ids": displayed_rules,
    }
    return append_audit_event(log_path, "clinician_triage_decision", patient_id, details)


def append_audit_event(
    log_path: str | Path, event_type: str, patient_id: str, details: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Append one timestamped event using the shared JSONL audit format."""
    if not event_type or not patient_id:
        raise ValueError("event_type and patient_id are required")
    reserved = {"event_id", "event_type", "timestamp", "patient_id", "schema_version"}
    if reserved.intersection(details or {}):
        raise ValueError("audit details cannot override reserved event fields")
    event = {
        "event_id": str(uuid4()), "event_type": event_type, "timestamp": _now(),
        "patient_id": patient_id, "schema_version": 1,
    }
    event.update(details or {})
    return _append_jsonl(log_path, event)


def _append_jsonl(log_path: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _AUDIT_LOCK, path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, separators=(",", ":")) + "\n")
        stream.flush()
    return event


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
