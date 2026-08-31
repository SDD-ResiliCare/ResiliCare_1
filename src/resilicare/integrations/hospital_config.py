"""Hospital-specific operational recommendations, isolated from clinical scoring."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

PROFILE_IDS = {"urban_trauma_center", "rural_clinic"}


@lru_cache(maxsize=1)
def load_hospital_profiles() -> dict[str, Any]:
    table = json.loads((Path(__file__).parent.parent / "config" / "hospital_profiles.json").read_text(encoding="utf-8"))
    if not table.get("simulated_profiles") or set(table.get("profiles", {})) != PROFILE_IDS:
        raise ValueError("exactly the two simulated hospital profiles are required")
    for profile_id, profile in table["profiles"].items():
        beds = profile.get("bed_counts", {})
        if any(type(beds.get(key)) is not int or beds[key] < 0 for key in ("ed", "inpatient", "icu")):
            raise ValueError(f"{profile_id} bed counts must be non-negative integers")
        if type(profile.get("icu_available")) is not bool or profile["icu_available"] != (beds["icu"] > 0):
            raise ValueError(f"{profile_id} ICU capability conflicts with ICU bed count")
        if not isinstance(profile.get("available_specialties"), list) or not profile.get("local_escalation_contacts"):
            raise ValueError(f"{profile_id} requires specialties and escalation contacts")
    return table


def get_hospital_profile(profile_id: str) -> dict[str, Any]:
    try:
        return load_hospital_profiles()["profiles"][profile_id]
    except KeyError as exc:
        raise ValueError(f"hospital profile must be one of: {', '.join(sorted(PROFILE_IDS))}") from exc


def _required_specialties(patient: Mapping[str, Any]) -> list[str]:
    complaint = str(patient.get("chief_complaint", "")).casefold()
    specialties = []
    if float(patient.get("age_years", 18)) < 18: specialties.append("pediatrics")
    keyword_routes = {
        "cardiology": ("chest",),
        "neurology": ("speech difficulty", "right-arm weakness", "new confusion"),
        "general_surgery": ("abdominal pain", "pelvic pain"),
        "psychiatry": ("suicidal", "self-harm"),
        "trauma": ("forearm cut", "fall"),
        "orthopedics": ("hip pain", "twisted ankle"),
        "urology": ("flank pain",),
    }
    for specialty, phrases in keyword_routes.items():
        if any(phrase in complaint for phrase in phrases): specialties.append(specialty)
    return list(dict.fromkeys(specialties))


def assess_hospital_operations(
    patient: Mapping[str, Any], ai_result: Mapping[str, Any], profile_id: str, *, queue_length: int,
) -> dict[str, Any]:
    """Return routing/capability flags without altering the clinical result."""
    if type(queue_length) is not int or queue_length < 0:
        raise ValueError("queue_length must be a non-negative integer")
    esi = ai_result.get("point_estimate")
    if type(esi) is not int or esi not in range(1, 6):
        raise ValueError("ai_result point_estimate must be ESI 1-5")
    profile = get_hospital_profile(profile_id)
    required = _required_specialties(patient)
    unavailable = [item for item in required if item not in profile["available_specialties"]]
    icu_may_be_needed = esi == 1 or patient.get("immediate_lifesaving_intervention") is True
    icu_alert = icu_may_be_needed and not profile["icu_available"]
    unsupported = bool(unavailable or icu_alert)
    transfer = unsupported and profile["transfer_capability"]["transfer_first_for_unsupported"]
    capacity_warning = queue_length >= profile["queue_capacity_warning_at"]
    contacts = profile["local_escalation_contacts"]
    contact = contacts.get("transfer_coordination") if transfer else next(
        (contacts[item] for item in required if item in contacts), contacts["default"],
    )
    care_area = profile["transfer_stabilization_area"] if transfer else profile["care_areas"][str(esi)]
    alerts = [f"Unavailable specialty: {item.replace('_', ' ')}" for item in unavailable]
    if icu_alert: alerts.append("No on-site ICU for a presentation that may require critical care")
    if capacity_warning:
        alerts.append(f"Capacity warning: queue {queue_length} reached local threshold {profile['queue_capacity_warning_at']}")
    status = "TRANSFER_RECOMMENDED" if transfer else "CAPACITY_WARNING" if capacity_warning else "LOCAL_CARE_AVAILABLE"
    recommendation = (
        "Stabilize locally and initiate clinician-led transfer coordination; receiving-facility acceptance is not verified."
        if transfer else "Use the configured local care area and escalate through the listed simulated contact."
    )
    return {
        "profile_id": profile_id, "profile_name": profile["display_name"], "facility_type": profile["facility_type"],
        "input_esi": esi, "clinical_priority_unchanged": True, "status": status,
        "required_specialties": required, "unavailable_specialties": unavailable,
        "icu_available": profile["icu_available"], "transfer_recommended": transfer,
        "transfer_capability": dict(profile["transfer_capability"]), "capacity_warning": capacity_warning,
        "queue_length": queue_length, "queue_capacity_warning_at": profile["queue_capacity_warning_at"],
        "bed_counts": dict(profile["bed_counts"]), "suggested_care_area": care_area,
        "escalation_contact": contact, "alerts": alerts, "recommendation": recommendation,
        "simulated_profile": True, "disclaimer": load_hospital_profiles()["disclaimer"],
    }
