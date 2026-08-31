"""Queue-pressure Combat Mode state, safety badges, and acknowledgement audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from src.core.safety_rules import append_audit_event
from src.data.audit_log import validate_clinician_identity
from src.workflows.queue_surge import COMBAT_MODE_QUEUE_THRESHOLD


def combat_mode_state(
    queue_length: int, *, manually_declared: bool = False, threshold: int = COMBAT_MODE_QUEUE_THRESHOLD,
) -> dict[str, Any]:
    if type(queue_length) is not int or queue_length < 0 or type(manually_declared) is not bool:
        raise ValueError("queue_length must be a non-negative integer and manually_declared must be boolean")
    if type(threshold) is not int or threshold < 1:
        raise ValueError("threshold must be a positive integer")
    automatic = queue_length >= threshold
    return {
        "active": automatic or manually_declared,
        "trigger": "QUEUE_LENGTH" if automatic else "MANUAL" if manually_declared else "NONE",
        "queue_length": queue_length,
        "threshold": threshold,
        "scoring_changed": False,
    }


def critical_safety_badge(ai_result: Mapping[str, Any]) -> dict[str, str]:
    rules = list(ai_result.get("matched_safety_rules") or [])
    lines = list(ai_result.get("explanation_lines") or [])
    reason = lines[0] if lines else ai_result.get("explanation_text") or "Clinician review remains required."
    if any(rule.startswith("IMMEDIATE.") for rule in rules):
        return {"level": "IMMEDIATE", "label": "Immediate action", "reason": reason}
    if any(rule.startswith("HIGH_RISK.") for rule in rules):
        return {"level": "HIGH_RISK", "label": "High-risk presentation", "reason": reason}
    if ai_result.get("mandatory_safety_workup"):
        return {"level": "SAFETY_WORKUP", "label": "Mandatory safety workup", "reason": reason}
    if ai_result.get("defer_to_senior_nurse"):
        return {"level": "REVIEW", "label": "Senior review required", "reason": reason}
    return {"level": "STANDARD", "label": "No critical rule matched", "reason": reason}


def record_combat_acknowledgement(
    log_path: str | Path, *, patient_id: str, clinician_id: str, clinician_role: str,
    ai_result: Mapping[str, Any], surge_state: Mapping[str, Any], safety_badge: Mapping[str, str],
) -> dict[str, Any]:
    if not isinstance(patient_id, str):
        raise ValueError("patient_id must be a string")
    patient_id = patient_id.strip()
    clinician_id, clinician_role = validate_clinician_identity(clinician_id, clinician_role)
    if not patient_id:
        raise ValueError("patient_id is required")
    if not surge_state.get("active"):
        raise ValueError("Combat Mode acknowledgement requires an active surge state")
    confidence = ai_result.get("confidence_score")
    if type(ai_result.get("point_estimate")) is not int or not isinstance(confidence, (int, float)):
        raise ValueError("current AI score and confidence are required")
    return append_audit_event(log_path, "combat_mode_acknowledgement", patient_id, {
        "clinician_id": clinician_id,
        "clinician_role": clinician_role,
        "current_ai": {
            "display_score": ai_result.get("display_score"),
            "point_estimate": ai_result["point_estimate"],
            "esi_set": list(ai_result.get("esi_set") or []),
            "confidence_score": confidence,
            "confidence_label": ai_result.get("confidence_label"),
            "badge": ai_result.get("badge"),
        },
        "surge_state": dict(surge_state),
        "safety_badge": dict(safety_badge),
    })
