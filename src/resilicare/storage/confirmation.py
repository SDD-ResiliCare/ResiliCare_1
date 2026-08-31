"""Explicit clinician confirmation state for safety-gated triage decisions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from resilicare.engine.safety import append_audit_event
from resilicare.storage.audit import validate_clinician_identity

CONFIRMATION_TIMEOUT_SECONDS = 15 * 60


def pending_confirmation(*, encounter_id: str, now: datetime | None = None) -> dict[str, Any]:
    if not isinstance(encounter_id, str) or not encounter_id.strip():
        raise ValueError("encounter_id is required")
    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("now must include a timezone")
    return {
        "encounter_id": encounter_id,
        "status": "PENDING_CLINICIAN_CONFIRMATION",
        "issued_at": issued_at.isoformat(),
        "expires_at": (issued_at + timedelta(seconds=CONFIRMATION_TIMEOUT_SECONDS)).isoformat(),
        "routing_allowed": False,
    }


def confirmation_status(record: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    state = dict(record)
    if state.get("status") == "CONFIRMED":
        state["routing_allowed"] = True
        return state
    if state.get("status") == "CLINICIAN_OVERRIDE":
        state["routing_allowed"] = False
        state.setdefault("review_action", "ROUTE_REEVALUATION_REQUIRED")
        return state
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must include a timezone")
    expires_at = datetime.fromisoformat(str(state["expires_at"]))
    if current >= expires_at:
        state.update({
            "status": "TIMED_OUT_SENIOR_REVIEW",
            "routing_allowed": False,
            "review_action": "SENIOR_REVIEW_REQUIRED",
            "message": "Clinician confirmation timed out; retain the safety-capped ESI and escalate for senior review.",
        })
    else:
        state["routing_allowed"] = False
    return state


def record_clinician_confirmation(
    log_path: str | Path,
    *,
    patient_id: str,
    encounter_id: str,
    clinician_id: str,
    clinician_role: str,
    ai_result: Mapping[str, Any],
) -> dict[str, Any]:
    clinician_id, clinician_role = validate_clinician_identity(clinician_id, clinician_role)
    point_estimate = ai_result.get("point_estimate")
    if type(point_estimate) is not int or point_estimate not in range(1, 6):
        raise ValueError("current canonical ESI is required")
    if not patient_id or not encounter_id:
        raise ValueError("patient_id and encounter_id are required")
    return append_audit_event(log_path, "clinician_triage_confirmation", patient_id, {
        "encounter_id": encounter_id,
        "clinician_id": clinician_id,
        "clinician_role": clinician_role,
        "confirmed_esi": point_estimate,
        "displayed_safety_rules": list(ai_result.get("explanation_rule_ids") or [])[:2],
        "matched_safety_rules": list(ai_result.get("matched_safety_rules") or []),
    })
