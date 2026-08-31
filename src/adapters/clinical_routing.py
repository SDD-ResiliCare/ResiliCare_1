"""Safety-gated routing over explicitly simulated scheme and facility data."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from src.core.confidence_scoring import score_with_confidence
from src.core.safety_rules import evaluate_safety_rules

VALID_SCHEMES = {"PM-JAY", "ESIC", "Private Insurer X", "Self-pay"}


@lru_cache(maxsize=1)
def load_facility_table() -> dict[str, Any]:
    table = json.loads((Path(__file__).parent.parent / "config" / "facilities.json").read_text(encoding="utf-8"))
    if not table.get("simulated_data") or not table.get("fictional_facilities") or table.get("live_nhcx_integration"):
        raise ValueError("facility table must remain explicitly simulated, fictional, and offline")
    return table


def suggest_scheme_route(
    patient: Mapping[str, Any], confirmed_esi: int, *, clinician_confirmed: bool,
    safety_result: Mapping[str, Any] | None = None,
    confidence_result: Mapping[str, Any] | None = None,
    operational_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Suggest a financial route only after clinical safety and uncertainty gates pass."""
    scheme = patient.get("scheme")
    if scheme not in VALID_SCHEMES:
        raise ValueError("scheme must be PM-JAY, ESIC, Private Insurer X, or Self-pay")
    if type(confirmed_esi) is not int or confirmed_esi not in range(1, 6) or type(clinician_confirmed) is not bool:
        raise ValueError("confirmed_esi must be 1-5 and clinician_confirmed must be boolean")
    safety = dict(safety_result or evaluate_safety_rules(dict(patient)))
    confidence = dict(confidence_result or score_with_confidence(dict(patient), confirmed_esi, safety_result=safety))
    blockers = []
    if safety.get("status") == "HARD_OVERRIDE": blockers.append("HARD_SAFETY_OVERRIDE")
    if confidence.get("mandatory_safety_workup"): blockers.append("MANDATORY_SAFETY_WORKUP")
    if patient.get("worsening_vitals") is True: blockers.append("WORSENING_VITALS")
    if confidence.get("defer_to_senior_nurse") or len(confidence.get("esi_set") or []) != 1:
        blockers.append("UNRESOLVED_ESI_UNCERTAINTY")

    result = {
        "patient_id": patient.get("patient_id"), "scheme": scheme, "confirmed_esi": confirmed_esi,
        "simulated_scheme_data": True, "live_nhcx_integration": False,
        "disclaimer": load_facility_table()["disclaimer"], "clinical_priority_unchanged": True,
        "blockers": list(dict.fromkeys(blockers)), "suggestions": [], "recommended_route": None,
        "operational_context": _operational_context(operational_context),
    }
    if confirmed_esi not in {4, 5}:
        return result | {"status": "NOT_LOW_ACUITY", "message": "Alternate financial routing is limited to clinician-confirmed ESI 4/5."}
    if blockers:
        return result | {"status": "CLINICAL_ROUTING_BLOCKED", "message": "Clinical safety or uncertainty must be resolved before financial routing."}
    if not clinician_confirmed:
        return result | {"status": "CLINICIAN_CONFIRMATION_REQUIRED", "message": "Confirm ESI 4/5 before showing an alternate facility."}

    suggestions = []
    for facility in load_facility_table()["facilities"]:
        terms = facility["scheme_terms"].get(scheme)
        if terms and confirmed_esi in facility["accepts_esi_levels"]:
            suggestions.append({
                "facility_id": facility["facility_id"], "facility_name": facility["name"],
                "facility_type": facility["facility_type"], "simulated_distance_km": facility["simulated_distance_km"],
                "accepted_scheme": scheme, "cashless_eligible": terms["cashless"],
                "room_rent_cap_inr_per_day": terms["room_rent_cap_inr_per_day"],
                "tag": (f"Cashless eligible at {facility['name']}" if terms["cashless"] else
                        f"{scheme} accepted at {facility['name']} — cashless not available"),
            })
    suggestions.sort(key=lambda item: (not item["cashless_eligible"], item["simulated_distance_km"], item["facility_name"]))
    return result | {
        "status": "ROUTE_SUGGESTED" if suggestions else "NO_MATCHING_FACILITY",
        "message": "Simulated alternate facility options found." if suggestions else "No simulated facility accepts this scheme.",
        "suggestions": suggestions, "recommended_route": suggestions[0] if suggestions else None,
        "reasoning": _route_reasoning(suggestions[0], scheme, operational_context) if suggestions else None,
    }


def _operational_context(context: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not context:
        return None
    return {key: context.get(key) for key in (
        "profile_id", "profile_name", "queue_length", "queue_capacity_warning_at", "capacity_warning",
    )}


def _route_reasoning(route: Mapping[str, Any], scheme: str, context: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "scheme": f"{scheme} is accepted by the suggested fictional facility.",
        "distance": f"Simulated distance: {route['simulated_distance_km']} km.",
        "current_hospital_capacity": (
            "Current simulated hospital capacity is under its warning threshold."
            if not context or not context.get("capacity_warning") else
            "Current simulated hospital queue has reached its capacity-warning threshold."
        ),
    }
