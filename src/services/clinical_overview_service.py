"""Deterministic, auditable explanations for triage and care-team allocation."""

from collections.abc import Mapping
from typing import Any
from uuid import UUID


def build_triage_overview(
    result: Mapping[str, Any], *, ward_id: UUID | None, ward_name: str | None
) -> tuple[str, dict[str, Any]]:
    """Explain the clinical recommendation without implying autonomous assignment."""
    clinical_reason = str(result.get("explanation_text") or "Clinical inputs require clinician review.").strip()
    ward_reason = (
        f"Hospital routing maps the recommended ESI {result['point_estimate']} to {ward_name}."
        if ward_name
        else f"No ward mapping is configured for recommended ESI {result['point_estimate']}."
    )
    review = (
        "Senior nurse review is required before assignment."
        if result.get("defer_to_senior_nurse")
        else "A nurse or clinician must confirm the recommendation before assignment."
    )
    factors = {
        "recommended_esi": result["point_estimate"],
        "possible_esi_levels": list(result.get("esi_set") or []),
        "confidence_label": result.get("confidence_label"),
        "requires_senior_review": bool(result.get("defer_to_senior_nurse")),
        "explanation_lines": list(result.get("explanation_lines") or []),
        "explanation_rule_ids": list(result.get("explanation_rule_ids") or []),
        "matched_safety_rules": list(result.get("matched_safety_rules") or []),
        "uncertainty_reasons": list(result.get("uncertainty_reasons") or []),
        "recommended_ward_id": str(ward_id) if ward_id else None,
        "recommended_ward_name": ward_name,
        "method": "RULE_TEMPLATE",
    }
    return f"{clinical_reason} {ward_reason} {review}", factors


def build_allocation_overview(
    *,
    final_esi: int,
    ward_id: UUID,
    ward_name: str,
    suggested_ward_id: UUID | None,
    suggested_ward_name: str | None,
    doctor_id: UUID,
    doctor_name: str,
    doctor_was_busy: bool,
    doctor_queue_position: int | None,
    allocator_reason: str,
) -> tuple[str, dict[str, Any]]:
    """Explain a confirmed human allocation using configuration and workload facts."""
    ward_matches = suggested_ward_id == ward_id if suggested_ward_id else None
    if ward_matches:
        ward_reason = f"{ward_name} matches the hospital routing rule for confirmed ESI {final_esi}."
    elif suggested_ward_name:
        ward_reason = (
            f"The allocator selected {ward_name} instead of the configured suggestion "
            f"{suggested_ward_name}; recorded reason: {allocator_reason}."
        )
    else:
        ward_reason = f"The allocator selected {ward_name}; recorded reason: {allocator_reason}."

    if doctor_was_busy:
        position_text = (
            f" at position {doctor_queue_position}" if doctor_queue_position is not None else ""
        )
        doctor_reason = (
            f"{doctor_name} is assigned to this ward and is currently busy, so the patient is "
            f"waiting{position_text} in that doctor's queue."
        )
    else:
        doctor_reason = f"{doctor_name} is assigned to this ward and was free, so care starts immediately."
    factors = {
        "final_esi": final_esi,
        "ward_id": str(ward_id),
        "ward_name": ward_name,
        "suggested_ward_id": str(suggested_ward_id) if suggested_ward_id else None,
        "suggested_ward_name": suggested_ward_name,
        "ward_matches_suggestion": ward_matches,
        "doctor_staff_id": str(doctor_id),
        "doctor_name": doctor_name,
        "doctor_was_busy": doctor_was_busy,
        "doctor_queue_position": doctor_queue_position,
        "allocator_reason": allocator_reason,
        "method": "RULE_TEMPLATE",
    }
    return f"{ward_reason} {doctor_reason}", factors
