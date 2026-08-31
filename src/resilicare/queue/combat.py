"""Queue-pressure Combat Mode state, safety badges, and acknowledgement audit."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from resilicare.engine.safety import append_audit_event
from resilicare.queue.surge import COMBAT_MODE_QUEUE_THRESHOLD


def combat_mode_state(queue_length: int, *, manually_declared: bool = False) -> dict[str, Any]:
    if type(queue_length) is not int or queue_length < 0 or type(manually_declared) is not bool:
        raise ValueError("queue_length must be a non-negative integer and manually_declared must be boolean")
    automatic = queue_length >= COMBAT_MODE_QUEUE_THRESHOLD
    return {
        "active": automatic or manually_declared,
        "trigger": "QUEUE_LENGTH" if automatic else "MANUAL" if manually_declared else "NONE",
        "queue_length": queue_length,
        "threshold": COMBAT_MODE_QUEUE_THRESHOLD,
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
    log_path: str | Path, *, patient_id: str, clinician_id: str,
    ai_result: Mapping[str, Any], surge_state: Mapping[str, Any], safety_badge: Mapping[str, str],
) -> dict[str, Any]:
    if not isinstance(patient_id, str) or not isinstance(clinician_id, str):
        raise ValueError("patient_id and clinician_id must be strings")
    patient_id, clinician_id = patient_id.strip(), clinician_id.strip()
    if not patient_id or not clinician_id:
        raise ValueError("patient_id and clinician_id are required")
    if len(clinician_id) > 80:
        raise ValueError("clinician_id is too long")
    if not surge_state.get("active"):
        raise ValueError("Combat Mode acknowledgement requires an active surge state")
    confidence = ai_result.get("confidence_score")
    if type(ai_result.get("point_estimate")) is not int or not isinstance(confidence, (int, float)):
        raise ValueError("current AI score and confidence are required")
    return append_audit_event(log_path, "combat_mode_acknowledgement", patient_id, {
        "clinician_id": clinician_id,
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
