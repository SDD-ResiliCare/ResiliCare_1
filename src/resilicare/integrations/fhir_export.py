"""FHIR-shaped prototype export; intentionally not a conformance claim."""

from __future__ import annotations

from typing import Any, Mapping

FHIR_SHAPED_DISCLAIMER = (
    "FHIR-shaped prototype JSON; not validated as a conformant FHIR resource and not transmitted to ABDM or an EHR."
)

_OBSERVATIONS = {
    "hr_bpm": ("8867-4", "Heart rate", "/min"),
    "rr_bpm": ("9279-1", "Respiratory rate", "/min"),
    "spo2_pct": ("59408-5", "Oxygen saturation", "%"),
    "sbp_mmhg": ("8480-6", "Systolic blood pressure", "mm[Hg]"),
    "dbp_mmhg": ("8462-4", "Diastolic blood pressure", "mm[Hg]"),
    "temp_c": ("8310-5", "Body temperature", "Cel"),
}


def build_fhir_shaped_bundle(patient: Mapping[str, Any], encounter: Mapping[str, Any]) -> dict[str, Any]:
    patient_id, encounter_id = patient["patient_uid"], encounter["encounter_id"]
    gender = {"Female": "female", "Male": "male"}.get(patient.get("sex_at_birth"), "unknown")
    patient_resource = {
        "resourceType": "Patient", "id": patient_id, "active": True, "gender": gender,
        "identifier": [{"system": "urn:resilicare:patient", "value": patient_id}],
        "extension": [
            {"url": "https://resilicare.local/scheme", "valueString": patient.get("scheme") or "Unknown"},
            {"url": "https://resilicare.local/synthetic", "valueBoolean": True},
        ],
    }
    decision = encounter.get("final_clinician_decision") or {}
    encounter_resource = {
        "resourceType": "Encounter", "id": encounter_id,
        "status": "finished" if decision.get("decision") != "pending" else "in-progress",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "EMER"},
        "subject": {"reference": f"Patient/{patient_id}"},
        "period": {"start": encounter.get("occurred_at")},
        "reasonCode": [{"text": encounter.get("chief_complaint")}],
        "extension": [
            {"url": "https://resilicare.local/suggested-esi", "valueString": encounter["suggested_esi"].get("badge")},
            {"url": "https://resilicare.local/final-decision", "valueString": decision.get("decision", "pending")},
            {"url": "https://resilicare.local/safety-flags", "valueString": "; ".join(
                f"{flag.get('label')}: {flag.get('reason')}" for flag in encounter.get("safety_flags", [])
            )},
        ],
    }
    
    overridden_esi = decision.get("overridden_esi") or decision.get("final_esi")
    if overridden_esi is not None and decision.get("decision") == "override":
        encounter_resource["extension"].append(
            {"url": "https://resilicare.local/overridden-esi", "valueInteger": int(overridden_esi)}
        )

    entries = [{"resource": patient_resource}, {"resource": encounter_resource}]
    for key, (code, display, unit) in _OBSERVATIONS.items():
        value = encounter.get("vitals", {}).get(key)
        if value is None:
            continue
        entries.append({"resource": {
            "resourceType": "Observation", "id": f"{encounter_id}-{key}", "status": "final",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/observation-category", "code": "vital-signs"}]}],
            "code": {"coding": [{"system": "http://loinc.org", "code": code, "display": display}]},
            "subject": {"reference": f"Patient/{patient_id}"},
            "encounter": {"reference": f"Encounter/{encounter_id}"},
            "effectiveDateTime": encounter.get("occurred_at"),
            "valueQuantity": {"value": value, "unit": unit, "system": "http://unitsofmeasure.org", "code": unit},
        }})
    return {
        "resourceType": "Bundle", "type": "collection", "timestamp": encounter.get("occurred_at"),
        "identifier": {"system": "urn:resilicare:fhir-shaped-bundle", "value": f"bundle-{encounter_id}"},
        "extension": [{"url": "https://resilicare.local/fhir-shaped-disclaimer", "valueString": FHIR_SHAPED_DISCLAIMER}],
        "entry": entries,
    }
