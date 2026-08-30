"""Append-only audit records for AI suggestions and clinician overrides."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .safety import append_audit_event

REASON_CODES = {
    "CLINICAL_DETERIORATION": "Clinical deterioration",
    "ADDITIONAL_HISTORY": "Additional history became available",
    "EXAMINATION_FINDINGS": "Clinical examination findings",
    "VITAL_SIGN_CONCERN": "Vital-sign concern",
    "RESOURCE_NEED_CHANGE": "Expected resource need changed",
    "AI_DISAGREEMENT": "Clinician disagrees with AI assessment",
    "OTHER": "Other",
}


def record_clinician_override(
    log_path: str | Path,
    *,
    patient_id: str,
    clinician_id: str,
    original_ai_result: Mapping[str, Any],
    overridden_esi: int,
    reason_code: str,
    reason_text: str,
) -> dict[str, Any]:
    """Validate and append one override; no update/delete operation is exposed."""
    patient_id, clinician_id, reason_text = patient_id.strip(), clinician_id.strip(), reason_text.strip()
    point = original_ai_result.get("point_estimate")
    confidence = original_ai_result.get("confidence_score")
    if not patient_id or not clinician_id:
        raise ValueError("patient_id and clinician_id are required")
    if type(point) is not int or type(overridden_esi) is not int or point not in range(1, 6) or overridden_esi not in range(1, 6):
        raise ValueError("original and overridden ESI must be between 1 and 5")
    if overridden_esi == point:
        raise ValueError("overridden ESI must differ from the AI point estimate")
    if reason_code not in REASON_CODES or not reason_text:
        raise ValueError("a valid reason_code and free-text reason are required")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        raise ValueError("original AI confidence is required")
    esi_set = list(original_ai_result.get("esi_set") or [point])
    if not esi_set or any(type(level) is not int or level not in range(1, 6) for level in esi_set):
        raise ValueError("original AI ESI set is invalid")
    if len(clinician_id) > 80 or len(reason_text) > 2000:
        raise ValueError("clinician_id or reason_text is too long")

    return append_audit_event(log_path, "clinician_esi_override", patient_id, {
        "clinician_id": clinician_id,
        "decision": "override",
        "original_ai": {
            "display_score": original_ai_result.get("display_score"),
            "point_estimate": point,
            "esi_set": esi_set,
            "confidence_score": confidence,
            "confidence_label": original_ai_result.get("confidence_label"),
            "confidence_method": original_ai_result.get("confidence_method"),
            "badge": original_ai_result.get("badge"),
            "explanation_text": original_ai_result.get("explanation_text"),
            "explanation_rule_ids": list(original_ai_result.get("explanation_rule_ids") or []),
            "mandatory_safety_workup": bool(original_ai_result.get("mandatory_safety_workup")),
            "ambiguous_presentations": list(original_ai_result.get("ambiguous_presentations") or []),
        },
        "overridden_esi": overridden_esi,
        "override_direction": "escalation" if overridden_esi < point else "de_escalation",
        "reason": {"code": reason_code, "label": REASON_CODES[reason_code], "free_text": reason_text},
    })


def read_audit_events(
    log_path: str | Path, *, patient_id: str | None = None, event_type: str | None = None
) -> list[dict[str, Any]]:
    """Read, optionally filter, but never alter the JSONL ledger."""
    path = Path(log_path)
    if not path.exists():
        return []
    events = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid audit JSON on line {line_number}") from exc
        if (patient_id is None or event.get("patient_id") == patient_id) and (
            event_type is None or event.get("event_type") == event_type
        ):
            events.append(event)
    return events
