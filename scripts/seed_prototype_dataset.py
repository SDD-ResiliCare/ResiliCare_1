"""Seed the normalized Supabase schema from the compact prototype CSV package.

The command is a dry run unless ``--apply`` is supplied. IDs are deterministic,
so rerunning the command updates only this synthetic seed set and never deletes
unrelated rows. By default only the 40 patients marked LIVE are imported.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from supabase import Client, create_client

ROOT = Path(__file__).parents[1]
CSV_DIR = ROOT / "data" / "prototype_dataset_v1" / "csv"
SEED_NAMESPACE = UUID("34f75f0a-871d-47b5-9658-04b76e06b409")
DEMO_DATE = "2026-09-02"


def _rows(name: str) -> list[dict[str, str]]:
    with (CSV_DIR / name).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _id(kind: str, external_id: str) -> str:
    return str(uuid5(SEED_NAMESPACE, f"{kind}:{external_id}"))


def _bool(value: str) -> bool:
    return value.casefold() == "true"


def _int(value: str) -> int | None:
    return int(value) if value else None


def _float(value: str) -> float | None:
    return float(value) if value else None


def _nullable(value: str) -> str | None:
    return value or None


def _split_name(full_name: str) -> tuple[str, str | None]:
    first_name, _, last_name = full_name.strip().partition(" ")
    return first_name, last_name or None


def _load_local_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_seed_plan(include_reserve: bool = False) -> list[tuple[str, str, list[dict[str, Any]]]]:
    hospital_rows = _rows("hospitals.csv")
    ward_rows = _rows("wards.csv")
    staff_rows = _rows("staff.csv")
    patient_rows = [
        row for row in _rows("patients.csv") if include_reserve or row["dataset_status"] == "LIVE"
    ]
    encounter_rows = _rows("encounters.csv")
    doctor_rows = _rows("doctor_assignments.csv")
    nurse_rows = _rows("nurse_assignments.csv")
    vital_rows = _rows("vital_observations.csv")
    interview_rows = _rows("symptom_interviews.csv")
    assessment_rows = _rows("triage_assessments.csv")

    hospital_ids = {row["hospital_id"]: _id("hospital", row["hospital_id"]) for row in hospital_rows}
    ward_ids = {row["ward_id"]: _id("ward", row["ward_id"]) for row in ward_rows}
    staff_ids = {row["staff_id"]: _id("staff", row["staff_id"]) for row in staff_rows}
    patient_ids = {row["patient_id"]: _id("patient", row["patient_id"]) for row in patient_rows}
    encounter_ids = {row["encounter_id"]: _id("encounter", row["encounter_id"]) for row in encounter_rows}
    doctor_participant_ids = {
        row["doctor_assignment_id"]: _id("encounter_participant", row["doctor_assignment_id"])
        for row in doctor_rows
    }
    interview_ids = {
        row["symptom_interview_id"]: _id("symptom_interview", row["symptom_interview_id"])
        for row in interview_rows
    }
    vital_ids = {
        row["vital_observation_id"]: _id("vital_observation", row["vital_observation_id"])
        for row in vital_rows
    }
    config_ids = {
        row["hospital_id"]: _id(
            "hospital_operational_config", f"{row['hospital_id']}:{row['config_code']}"
        )
        for row in hospital_rows
    }
    queue_ids = {
        row["queue_session_id"]: _id("queue", row["queue_session_id"])
        for row in _rows("queue_sessions.csv")
    }

    hospitals = [
        {
            "id": hospital_ids[row["hospital_id"]],
            "hospital_code": row["hospital_id"],
            "name": row["hospital_name"],
            "facility_type": row["facility_level"].casefold(),
            "address": {"city": row["city"], "country": "India", "synthetic": True},
            "timezone": "Asia/Kolkata",
            "outbound_transfer_enabled": _bool(row["outbound_transfer_enabled"]),
            "status": "active",
        }
        for row in hospital_rows
    ]

    wards = [
        {
            "id": ward_ids[row["ward_id"]],
            "hospital_id": hospital_ids[row["hospital_id"]],
            "ward_code": row["ward_id"],
            "name": row["ward_name"],
            "ward_type": row["ward_type"].casefold(),
            "contact_extension": _nullable(row["contact_extension"]),
            "capacity": _int(row["total_beds"]),
            "status": "active" if _bool(row["is_active"]) else "inactive",
        }
        for row in ward_rows
    ]

    staff = []
    clinical_profiles = []
    for row in staff_rows:
        first_name, last_name = _split_name(row["full_name"])
        staff.append(
            {
                "id": staff_ids[row["staff_id"]],
                "hospital_id": hospital_ids[row["hospital_id"]],
                "employee_code": row["staff_id"],
                "staff_type": row["staff_role"].casefold(),
                "first_name": first_name,
                "last_name": last_name,
                "employment_status": "active" if _bool(row["is_active"]) else "inactive",
                "joined_on": "2026-01-01",
            }
        )
        if row["staff_role"] in {"DOCTOR", "NURSE"}:
            clinical_profiles.append(
                {
                    "staff_id": staff_ids[row["staff_id"]],
                    "registration_number": row["demo_registration_number"],
                    "registration_authority": "Synthetic prototype registry",
                    "qualification": "Synthetic prototype credential",
                    "specialty": row["specialization"],
                    "professional_grade": row["staff_role"].casefold(),
                    "bio": "Synthetic record for ResiliCare prototype demonstrations only.",
                }
            )

    staff_assignments = [
        {
            "id": _id("staff_ward_assignment", row["staff_ward_assignment_id"]),
            "staff_id": staff_ids[row["staff_id"]],
            "ward_id": ward_ids[row["ward_id"]],
            "role_in_ward": row["assignment_type"].casefold(),
            "is_primary_ward": row["assignment_type"] == "PRIMARY",
            "assigned_from": f"{DEMO_DATE}T00:00:00+05:30",
        }
        for row in _rows("staff_ward_assignments.csv")
    ]

    operational_configs = []
    esi_rules = []
    wards_by_hospital: dict[str, list[dict[str, str]]] = {}
    for row in ward_rows:
        wards_by_hospital.setdefault(row["hospital_id"], []).append(row)
    for row in hospital_rows:
        is_well_equipped = row["facility_level"] == "WELL_EQUIPPED"
        operational_configs.append(
            {
                "id": config_ids[row["hospital_id"]],
                "hospital_id": hospital_ids[row["hospital_id"]],
                "version": int(row["operational_config_version"]),
                "queue_warning_threshold": 12 if is_well_equipped else 8,
                "surge_threshold": 24 if is_well_equipped else 16,
                "transfer_first_for_unsupported": not is_well_equipped,
                "effective_from": f"{DEMO_DATE}T00:00:00+05:30",
                "is_active": True,
                "config_hash": hashlib.sha256(row["config_code"].encode()).hexdigest(),
            }
        )
        hospital_wards = sorted(wards_by_hospital[row["hospital_id"]], key=lambda item: item["ward_id"])
        ward_for_esi = {1: 0, 2: 0, 3: 1, 4: 2, 5: 2}
        for esi_level, ward_index in ward_for_esi.items():
            ward = hospital_wards[ward_index]
            external_key = f"{row['hospital_id']}:ESI:{esi_level}"
            esi_rules.append(
                {
                    "id": _id("esi_care_area_rule", external_key),
                    "operational_config_id": config_ids[row["hospital_id"]],
                    "esi_level": esi_level,
                    "ward_id": ward_ids[ward["ward_id"]],
                    "priority": 1,
                    "is_default": True,
                }
            )

    patients = []
    identifiers = []
    conditions = []
    first_doctor_by_hospital = {
        hospital: staff_ids[next(row["staff_id"] for row in staff_rows if row["hospital_id"] == hospital and row["staff_role"] == "DOCTOR")]
        for hospital in hospital_ids
    }
    hospital_city = {row["hospital_id"]: row["city"] for row in hospital_rows}
    for row in patient_rows:
        first_name, last_name = _split_name(row["full_name"])
        patients.append(
            {
                "id": patient_ids[row["patient_id"]],
                "first_name": first_name,
                "last_name": last_name,
                "date_of_birth": row["date_of_birth"],
                "estimated_age_years": _float(row["age_years_at_demo"]),
                "sex_at_birth": row["sex"].casefold(),
                "phone": row["phone"],
                "email": row["email"],
                "address": {"city": hospital_city[row["hospital_id"]], "country": "India", "synthetic": True},
                "preferred_language": "en-IN",
                "status": "active",
            }
        )
        identifiers.append(
            {
                "id": _id("patient_identifier", row["patient_id"]),
                "patient_id": patient_ids[row["patient_id"]],
                "hospital_id": hospital_ids[row["hospital_id"]],
                "identifier_type": "mrn",
                "identifier_value": row["medical_record_number"],
                "valid_from": DEMO_DATE,
            }
        )
        if row["chronic_conditions"] != "None reported":
            conditions.append(
                {
                    "id": _id("patient_condition", f"{row['patient_id']}:{row['chronic_conditions']}"),
                    "patient_id": patient_ids[row["patient_id"]],
                    "condition_name": row["chronic_conditions"],
                    "clinical_status": "active",
                    "verification_status": "patient_reported",
                    "recorded_by_staff_id": first_doctor_by_hospital[row["hospital_id"]],
                    "notes": f"Synthetic history. Current medication report: {row['current_medications']}",
                }
            )

    queues = [
        {
            "id": queue_ids[row["queue_session_id"]],
            "hospital_id": hospital_ids[row["hospital_id"]],
            "ward_id": ward_ids[f"{row['hospital_id']}-W01"],
            "queue_code": row["session_code"],
            "name": f"{row['hospital_id']} prototype emergency queue",
            "queue_type": row["session_type"].casefold(),
            "status": row["status"].casefold(),
        }
        for row in _rows("queue_sessions.csv")
    ]

    assessment_by_encounter = {row["encounter_id"]: row for row in assessment_rows}
    doctor_by_encounter = {row["encounter_id"]: row for row in doctor_rows}
    nurse_by_encounter = {row["encounter_id"]: row for row in nurse_rows}
    encounter_by_id = {row["encounter_id"]: row for row in encounter_rows}
    confirmed_doctor_rows = [
        row
        for row in doctor_rows
        if assessment_by_encounter[row["encounter_id"]]["clinician_confirmation_status"] == "CONFIRMED"
    ]
    current_assignment_ids = set()
    for doctor_external_id in {row["doctor_staff_id"] for row in confirmed_doctor_rows}:
        assignments = sorted(
            (row for row in confirmed_doctor_rows if row["doctor_staff_id"] == doctor_external_id),
            key=lambda row: (
                encounter_by_id[row["encounter_id"]]["status"] != "UNDER_ASSESSMENT",
                row["assigned_at"],
            ),
        )
        current_assignment_ids.add(assignments[0]["doctor_assignment_id"])
    patient_source = {row["patient_id"]: row for row in patient_rows}
    encounters = []
    queue_entries = []
    location_history = []
    coverages = []
    for row in encounter_rows:
        assessment = assessment_by_encounter[row["encounter_id"]]
        allocation_confirmed = assessment["clinician_confirmation_status"] == "CONFIRMED"
        doctor = doctor_by_encounter[row["encounter_id"]]
        doctor_is_current = doctor["doctor_assignment_id"] in current_assignment_ids
        nurse = nurse_by_encounter[row["encounter_id"]]
        patient = patient_source[row["patient_id"]]
        encounters.append(
            {
                "id": encounter_ids[row["encounter_id"]],
                "hospital_id": hospital_ids[row["hospital_id"]],
                "patient_id": patient_ids[row["patient_id"]],
                "encounter_code": row["encounter_code"],
                "encounter_type": "emergency",
                "status": "in_care" if doctor_is_current else row["status"].casefold(),
                "arrival_mode": row["arrival_mode"].casefold(),
                "arrived_at": row["arrival_at"],
                "triaged_at": assessment["assessed_at"],
                "care_started_at": doctor["assigned_at"] if doctor_is_current else None,
                "current_ward_id": ward_ids[row["current_ward_id"]] if allocation_confirmed else None,
                "chief_complaint": row["chief_complaint"],
                "presenting_details": (
                    f"{row['symptom_onset_text']}; scenario={row['scenario_category']}; "
                    f"demo_feature={row['special_demo_feature']}; disposition={row['recommended_disposition']}"
                ),
                "symptom_onset_precision": "approximate",
                "data_quality_notes": _nullable(row["data_quality_notes"]),
            }
        )
        queue_status = "completed" if allocation_confirmed else "waiting"
        queue_entries.append(
            {
                "id": _id("queue_entry", row["encounter_id"]),
                "queue_id": queue_ids[row["queue_session_id"]],
                "encounter_id": encounter_ids[row["encounter_id"]],
                "status": queue_status,
                "entered_at": row["arrival_at"],
                "called_at": doctor["assigned_at"] if allocation_confirmed else None,
                "exited_at": doctor["assigned_at"] if allocation_confirmed else None,
                "exit_reason": "allocated_to_doctor" if allocation_confirmed else None,
                "priority_boost": int(row["queue_priority_boost"]),
            }
        )
        if allocation_confirmed:
            location_history.append(
                {
                    "id": _id("encounter_location", row["encounter_id"]),
                    "encounter_id": encounter_ids[row["encounter_id"]],
                    "ward_id": ward_ids[row["current_ward_id"]],
                    "entered_at": doctor["assigned_at"],
                    "moved_by_staff_id": staff_ids[nurse["nurse_staff_id"]],
                    "transfer_reason": "Synthetic nurse-confirmed initial allocation",
                }
            )
        coverages.append(
            {
                "id": _id("encounter_coverage", row["encounter_id"]),
                "encounter_id": encounter_ids[row["encounter_id"]],
                "scheme_code": patient["coverage_scheme_code"],
                "payer_name": "Self pay" if patient["coverage_scheme_code"] == "SELF_PAY" else "Synthetic demo payer",
                "coverage_status": "active",
                "cashless_status": "not_applicable" if patient["coverage_scheme_code"] == "SELF_PAY" else "demo_verified",
            }
        )

    participants = [
        {
            "id": doctor_participant_ids[row["doctor_assignment_id"]],
            "encounter_id": encounter_ids[row["encounter_id"]],
            "staff_id": staff_ids[row["doctor_staff_id"]],
            "role": "primary_doctor",
            "assigned_at": row["assigned_at"],
            "ended_at": _nullable(row["released_at"]),
            "assigned_by_staff_id": staff_ids[nurse_by_encounter[row["encounter_id"]]["nurse_staff_id"]],
            "assignment_reason": row["assignment_reason"],
        }
        for row in doctor_rows
        if assessment_by_encounter[row["encounter_id"]]["clinician_confirmation_status"] == "CONFIRMED"
    ]
    participants.extend(
        {
            "id": _id("encounter_participant", row["nurse_assignment_id"]),
            "encounter_id": encounter_ids[row["encounter_id"]],
            "staff_id": staff_ids[row["nurse_staff_id"]],
            "role": row["nursing_role"].casefold(),
            "assigned_at": row["assigned_at"],
        }
        for row in nurse_rows
    )

    doctor_work_items = []
    for row in confirmed_doctor_rows:
        encounter = encounter_by_id[row["encounter_id"]]
        assessment = assessment_by_encounter[row["encounter_id"]]
        is_current = row["doctor_assignment_id"] in current_assignment_ids
        doctor_work_items.append(
            {
                "id": _id("doctor_work_item", row["doctor_assignment_id"]),
                "hospital_id": hospital_ids[encounter["hospital_id"]],
                "encounter_id": encounter_ids[row["encounter_id"]],
                "doctor_staff_id": staff_ids[row["doctor_staff_id"]],
                "ward_id": ward_ids[encounter["current_ward_id"]],
                "status": "in_service" if is_current else "waiting",
                "priority_esi": int(assessment["recommended_esi_level"]),
                "queued_at": row["assigned_at"],
                "started_at": row["assigned_at"] if is_current else None,
                "assigned_by_staff_id": staff_ids[nurse_by_encounter[row["encounter_id"]]["nurse_staff_id"]],
                "allocation_reason": "Synthetic nurse-confirmed initial allocation",
            }
        )

    questionnaire_id = _id("questionnaire", "DEMO-GENERAL-INTAKE:1:en-IN")
    questionnaires = [
        {
            "id": questionnaire_id,
            "code": "DEMO-GENERAL-INTAKE",
            "title": "Synthetic prototype symptom follow-up",
            "complaint_category": "general_emergency",
            "version": 1,
            "language_code": "en-IN",
            "is_active": True,
        }
    ]
    question_ids = {
        row["question_code"]: _id("questionnaire_question", row["question_code"])
        for row in _rows("symptom_question_templates.csv")
    }
    questions = [
        {
            "id": question_ids[row["question_code"]],
            "questionnaire_id": questionnaire_id,
            "question_code": row["question_code"],
            "question_text": row["question_text"],
            "answer_type": row["answer_type"].casefold(),
            "display_order": index,
            "clinical_rationale": f"Synthetic follow-up category: {row['question_category']}",
        }
        for index, row in enumerate(_rows("symptom_question_templates.csv"), start=1)
    ]
    interviews = [
        {
            "id": interview_ids[row["symptom_interview_id"]],
            "encounter_id": encounter_ids[row["encounter_id"]],
            "questionnaire_id": questionnaire_id,
            "interview_number": int(row["interview_number"]),
            "respondent_type": row["respondent_type"].casefold(),
            "conducted_by_staff_id": staff_ids[row["conducted_by_staff_id"]],
            "language_code": row["language_code"],
            "status": row["status"].casefold(),
            "started_at": row["started_at"],
            "completed_at": _nullable(row["completed_at"]),
        }
        for row in interview_rows
    ]
    responses = [
        {
            "id": _id("symptom_response", row["symptom_response_id"]),
            "interview_id": interview_ids[row["symptom_interview_id"]],
            "question_id": question_ids[row["question_code"]],
            "question_text_snapshot": row["question_text_snapshot"],
            "answer_value": {"value": row["answer_value"]},
            "answer_source": row["answer_source"].casefold(),
            "unable_to_answer": False,
            "notes": _nullable(row["notes"]),
            "answered_at": row["answered_at"],
        }
        for row in _rows("symptom_responses.csv")
    ]

    vitals = [
        {
            "id": vital_ids[row["vital_observation_id"]],
            "encounter_id": encounter_ids[row["encounter_id"]],
            "recorded_by_staff_id": staff_ids[row["recorded_by_staff_id"]],
            "source": row["source"].casefold(),
            "observed_at": row["observed_at"],
            "heart_rate_bpm": _float(row["heart_rate_bpm"]),
            "respiratory_rate_bpm": _float(row["respiratory_rate_per_min"]),
            "spo2_percent": _float(row["spo2_percent"]),
            "systolic_bp_mmhg": _float(row["systolic_bp_mmhg"]),
            "diastolic_bp_mmhg": _float(row["diastolic_bp_mmhg"]),
            "temperature_c": _float(row["temperature_c"]),
            "gcs_total": _int(row["gcs_total"]),
            "pain_score": _int(row["pain_score_0_10"]),
            "pain_scale": "NRS-0-10" if row["pain_score_0_10"] else None,
            "quality_notes": _nullable(row["quality_notes"]),
        }
        for row in vital_rows
    ]
    latest_vital_by_encounter: dict[str, dict[str, str]] = {}
    for row in vital_rows:
        current = latest_vital_by_encounter.get(row["encounter_id"])
        if current is None or int(row["observation_number"]) > int(current["observation_number"]):
            latest_vital_by_encounter[row["encounter_id"]] = row
    interview_by_encounter = {row["encounter_id"]: row for row in interview_rows}

    assessments = []
    safety_actions = []
    clinician_decisions = []
    for row in assessment_rows:
        encounter = next(item for item in encounter_rows if item["encounter_id"] == row["encounter_id"])
        latest_vital = latest_vital_by_encounter[row["encounter_id"]]
        assessment_id = _id("triage_assessment", row["triage_assessment_id"])
        input_snapshot = {
            "synthetic": True,
            "input_quality": row["input_quality"],
            "vital_observation_external_id": latest_vital["vital_observation_id"],
            "interview_external_id": interview_by_encounter[row["encounter_id"]]["symptom_interview_id"],
        }
        serialized_input = json.dumps(input_snapshot, sort_keys=True, separators=(",", ":"))
        assessments.append(
            {
                "id": assessment_id,
                "encounter_id": encounter_ids[row["encounter_id"]],
                "assessment_number": int(row["assessment_version"]),
                "latest_vital_observation_id": vital_ids[latest_vital["vital_observation_id"]],
                "source_interview_id": interview_ids[
                    interview_by_encounter[row["encounter_id"]]["symptom_interview_id"]
                ],
                "operational_config_id": config_ids[encounter["hospital_id"]],
                "assessment_status": row["clinician_confirmation_status"].casefold(),
                "proposed_esi": int(row["recommended_esi_level"]),
                "maximum_allowed_esi": _int(row["maximum_allowed_esi_level"]),
                "recommended_esi": int(row["recommended_esi_level"]),
                "possible_esi_levels": [int(row["recommended_esi_level"])],
                "uncertainty_label": "limited_input" if row["input_quality"] != "COMPLETE" else "prototype",
                "requires_senior_review": _bool(row["mandatory_safety_workup"]),
                "matched_safety_rules": {"prototype_mandatory_workup": _bool(row["mandatory_safety_workup"])},
                "matched_clinical_pathways": {},
                "missing_input_flags": [] if row["input_quality"] == "COMPLETE" else ["prototype_incomplete_input"],
                "input_snapshot": input_snapshot,
                "input_hash": hashlib.sha256(serialized_input.encode()).hexdigest(),
                "score_source": row["score_source"].casefold(),
                "engine_version": row["engine_version"],
                "confirmation_due_at": _nullable(row["confirmation_due_at"]),
                "created_by_staff_id": staff_ids[nurse_by_encounter[row["encounter_id"]]["nurse_staff_id"]],
            }
        )
        if _bool(row["mandatory_safety_workup"]):
            safety_actions.append(
                {
                    "id": _id("assessment_safety_action", row["triage_assessment_id"]),
                    "assessment_id": assessment_id,
                    "action_code": "PROTOTYPE_CLINICIAN_REVIEW",
                    "instruction": "Synthetic demo safety action: clinician review is required.",
                    "severity": "high",
                    "status": "acknowledged" if row["clinician_confirmation_status"] == "CONFIRMED" else "pending",
                    "due_at": _nullable(row["confirmation_due_at"]),
                    "acknowledged_by_staff_id": (
                        staff_ids[doctor_by_encounter[row["encounter_id"]]["doctor_staff_id"]]
                        if row["clinician_confirmation_status"] == "CONFIRMED"
                        else None
                    ),
                    "acknowledged_at": (
                        row["assessed_at"] if row["clinician_confirmation_status"] == "CONFIRMED" else None
                    ),
                }
            )
        if row["clinician_confirmation_status"] == "CONFIRMED":
            clinician_decisions.append(
                {
                    "id": _id("clinician_decision", row["triage_assessment_id"]),
                    "assessment_id": assessment_id,
                    "decision_type": "accepted",
                    "final_esi": int(row["recommended_esi_level"]),
                    "decided_by_staff_id": staff_ids[nurse_by_encounter[row["encounter_id"]]["nurse_staff_id"]],
                    "reason_code": "prototype_confirmation",
                    "reason_text": "Synthetic demo confirmation; not a real clinical decision.",
                    "decided_at": row["assessed_at"],
                }
            )

    prescriptions = [
        {
            "id": _id("prescription", row["prescription_id"]),
            "encounter_id": encounter_ids[row["encounter_id"]],
            "prescriber_participant_id": doctor_participant_ids[row["prescriber_assignment_id"]],
            "prescription_number": row["prescription_number"],
            "status": row["status"].casefold(),
            "revision_number": 1,
            "diagnosis_summary": _nullable(row["diagnosis_summary"]),
            "general_instructions": _nullable(row["general_instructions"]),
            "issued_at": _nullable(row["issued_at"]),
        }
        for row in _rows("prescriptions.csv")
    ]
    prescription_items = [
        {
            "id": _id("prescription_item", row["prescription_item_id"]),
            "prescription_id": _id("prescription", row["prescription_id"]),
            "generic_name": row["generic_name"],
            "dosage_form": row["dosage_form"],
            "strength": row["strength"],
            "dose": row["dose"],
            "route": row["route"],
            "frequency": row["frequency"],
            "duration_value": _int(row["duration_value"]),
            "duration_unit": _nullable(row["duration_unit"]),
            "quantity": _float(row["quantity"]),
            "is_prn": False,
            "instructions": row["instructions"],
        }
        for row in _rows("prescription_items.csv")
    ]

    receptionist_by_hospital = {
        hospital: staff_ids[
            next(
                row["staff_id"]
                for row in staff_rows
                if row["hospital_id"] == hospital and row["staff_role"] == "RECEPTIONIST"
            )
        ]
        for hospital in hospital_ids
    }
    encounter_source = {row["encounter_id"]: row for row in encounter_rows}
    invoices = [
        {
            "id": _id("invoice", row["invoice_id"]),
            "encounter_id": encounter_ids[row["encounter_id"]],
            "invoice_number": row["invoice_number"],
            "invoice_version": 1,
            "status": row["status"].casefold(),
            "currency_code": row["currency_code"],
            "subtotal": float(row["subtotal"]),
            "discount_total": float(row["discount_total"]),
            "tax_total": float(row["tax_total"]),
            "grand_total": float(row["grand_total"]),
            "amount_paid": float(row["amount_paid"]),
            "balance_due": float(row["balance_due"]),
            "issued_at": _nullable(row["issued_at"]),
            "created_by_staff_id": receptionist_by_hospital[
                encounter_source[row["encounter_id"]]["hospital_id"]
            ],
        }
        for row in _rows("invoices.csv")
    ]
    invoice_items = [
        {
            "id": _id("invoice_item", row["invoice_item_id"]),
            "invoice_id": _id("invoice", row["invoice_id"]),
            "service_code": row["service_code"],
            "category": row["category"].casefold(),
            "description": row["description"],
            "quantity": float(row["quantity"]),
            "unit_price": float(row["unit_price"]),
            "discount_amount": float(row["discount_amount"]),
            "tax_amount": float(row["tax_amount"]),
            "line_total": float(row["line_total"]),
        }
        for row in _rows("invoice_items.csv")
    ]
    feedback = [
        {
            "id": _id("feedback_submission", row["feedback_id"]),
            "encounter_id": encounter_ids[row["encounter_id"]],
            "hospital_id": hospital_ids[row["hospital_id"]],
            "category": row["category"].casefold(),
            "rating": _int(row["rating_1_5"]),
            "message": row["message"],
            "contact_permission": _bool(row["contact_permission"]),
            "status": row["status"].casefold(),
        }
        for row in _rows("feedback_submissions.csv")
    ]

    return [
        ("hospitals", "id", hospitals),
        ("wards", "id", wards),
        ("staff", "id", staff),
        ("clinical_staff_profiles", "staff_id", clinical_profiles),
        ("staff_ward_assignments", "id", staff_assignments),
        ("hospital_operational_configs", "id", operational_configs),
        ("esi_care_area_rules", "id", esi_rules),
        ("patients", "id", patients),
        ("patient_identifiers", "id", identifiers),
        ("patient_conditions", "id", conditions),
        ("queues", "id", queues),
        ("encounters", "id", encounters),
        ("queue_entries", "id", queue_entries),
        ("encounter_location_history", "id", location_history),
        ("encounter_participants", "id", participants),
        ("doctor_work_items", "id", doctor_work_items),
        ("encounter_coverages", "id", coverages),
        ("questionnaires", "id", questionnaires),
        ("questionnaire_questions", "id", questions),
        ("symptom_interviews", "id", interviews),
        ("symptom_responses", "id", responses),
        ("vital_observations", "id", vitals),
        ("triage_assessments", "id", assessments),
        ("assessment_safety_actions", "id", safety_actions),
        ("clinician_decisions", "id", clinician_decisions),
        ("prescriptions", "id", prescriptions),
        ("prescription_items", "id", prescription_items),
        ("invoices", "id", invoices),
        ("invoice_items", "id", invoice_items),
        ("feedback_submissions", "id", feedback),
    ]


def _chunks(rows: list[dict[str, Any]], size: int = 100) -> Iterable[list[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def apply_seed(plan: list[tuple[str, str, list[dict[str, Any]]]]) -> None:
    _load_local_env()
    supabase_url = os.environ.get("SUPABASE_URL")
    server_key = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not server_key:
        raise RuntimeError("SUPABASE_URL and a server-only Supabase key are required")

    client: Client = create_client(supabase_url, server_key)
    for table, conflict_column, rows in plan:
        if not rows:
            continue
        written = 0
        for batch in _chunks(rows):
            response = client.table(table).upsert(batch, on_conflict=conflict_column).execute()
            written += len(response.data)
        print(f"{table}: {written} synthetic rows upserted")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Upsert the synthetic dataset into Supabase")
    parser.add_argument(
        "--include-reserve",
        action="store_true",
        help="Also import the 60 reserve profiles; omitted by default",
    )
    args = parser.parse_args()
    plan = build_seed_plan(include_reserve=args.include_reserve)
    counts = {table: len(rows) for table, _, rows in plan}
    print(json.dumps(counts, indent=2, sort_keys=True))
    if not args.apply:
        print("Dry run only. Add --apply to upsert these synthetic records.")
        return
    apply_seed(plan)


if __name__ == "__main__":
    main()
