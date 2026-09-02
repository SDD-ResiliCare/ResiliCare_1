from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

import src.db.models  # noqa: F401
from scripts.seed_prototype_dataset import build_seed_plan
from src.db.base import Base
from src.db.models.audit import AuditEvent
from src.db.models.encounter import (
    DoctorWorkItem,
    Encounter,
    EncounterLocationHistory,
    EncounterParticipant,
    QueueEntry,
)
from src.db.models.organization import EsiCareAreaRule, Ward
from src.db.models.triage import ClinicianDecision, TriageAssessment
from src.db.models.workforce import Staff, StaffWardAssignment
from src.main import app
from src.schemas.encounter import EncounterAllocationCreate
from src.services.encounter_service import EncounterService


def test_allocation_contract_requires_auditable_reason_and_timezone():
    with pytest.raises(ValidationError, match="at least 1 character"):
        EncounterAllocationCreate(
            ward_id=uuid4(),
            doctor_staff_id=uuid4(),
            confirmed_at=datetime.now(UTC),
            reason="",
        )
    with pytest.raises(ValidationError, match="must include a timezone"):
        EncounterAllocationCreate(
            ward_id=uuid4(),
            doctor_staff_id=uuid4(),
            confirmed_at=datetime.now(UTC).replace(tzinfo=None),
            reason="Nurse confirmed the care-area allocation",
        )


def test_nurse_allocation_and_enriched_queue_contracts_are_exposed():
    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/encounters/{encounter_id}/allocation"]
    queue_response = paths["/api/v1/queues/current/entries"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert queue_response["$ref"].endswith("/CurrentQueueResponse")


def test_schema_prevents_multiple_active_locations_for_one_encounter():
    location = Base.metadata.tables["encounter_location_history"]
    index = next(index for index in location.indexes if index.name == "uq_encounter_active_location")
    assert index.unique is True
    assert "exited_at IS NULL" in str(index.dialect_options["postgresql"]["where"])
    migration = (
        Path(__file__).parents[1] / "supabase" / "migrations" / "007_one_active_encounter_location.sql"
    ).read_text(encoding="utf-8")
    assert "create unique index uq_encounter_active_location" in migration.lower()


def test_prototype_seed_allocates_only_clinician_confirmed_encounters():
    plan = {table: rows for table, _, rows in build_seed_plan()}
    confirmed_assessments = {
        row["encounter_id"] for row in plan["triage_assessments"] if row["assessment_status"] == "confirmed"
    }
    pending_assessments = {
        row["encounter_id"] for row in plan["triage_assessments"] if row["assessment_status"] != "confirmed"
    }
    located_encounters = {row["encounter_id"] for row in plan["encounter_location_history"]}
    doctor_encounters = {
        row["encounter_id"] for row in plan["encounter_participants"] if row["role"] == "primary_doctor"
    }
    doctor_work_encounters = {row["encounter_id"] for row in plan["doctor_work_items"]}
    current_ward_by_encounter = {row["id"]: row["current_ward_id"] for row in plan["encounters"]}
    queue_by_encounter = {row["encounter_id"]: row for row in plan["queue_entries"]}
    assert located_encounters == confirmed_assessments
    assert doctor_encounters == confirmed_assessments
    assert doctor_work_encounters == confirmed_assessments
    current_doctors = [
        row["doctor_staff_id"] for row in plan["doctor_work_items"] if row["status"] == "in_service"
    ]
    assert len(current_doctors) == len(set(current_doctors))
    assert all(queue_by_encounter[encounter_id]["exited_at"] is not None for encounter_id in confirmed_assessments)
    assert all(queue_by_encounter[encounter_id]["exited_at"] is None for encounter_id in pending_assessments)
    assert all(current_ward_by_encounter[encounter_id] is None for encounter_id in pending_assessments)


@pytest.mark.asyncio
@pytest.mark.parametrize("doctor_busy", [False, True])
async def test_confirmed_allocation_persists_location_doctor_and_audit_together(doctor_busy):
    hospital_id = uuid4()
    encounter_id = uuid4()
    ward_id = uuid4()
    doctor_id = uuid4()
    nurse_id = uuid4()
    assessment_id = uuid4()
    decision_id = uuid4()
    confirmed_at = datetime.now(UTC)
    encounter = Encounter(
        id=encounter_id,
        hospital_id=hospital_id,
        patient_id=uuid4(),
        encounter_code="ENC-TEST",
        arrived_at=confirmed_at,
        chief_complaint="Synthetic test complaint",
        status="arrived",
    )
    queue_entry = QueueEntry(
        id=uuid4(), queue_id=uuid4(), encounter_id=encounter_id, entered_at=confirmed_at, status="waiting"
    )
    assessment = TriageAssessment(
        id=assessment_id,
        encounter_id=encounter_id,
        assessment_number=1,
        operational_config_id=uuid4(),
        assessment_status="confirmed",
        proposed_esi=3,
        recommended_esi=3,
        recommended_ward_id=ward_id,
        possible_esi_levels=[3],
        uncertainty_label="high_confidence",
        ai_overview="ESI 3 and Acute Care are recommended from the recorded encounter inputs.",
        ai_overview_factors={"recommended_esi": 3, "recommended_ward_id": str(ward_id)},
        input_snapshot={},
        input_hash="0" * 64,
        score_source="test",
        engine_version="test",
    )
    decision = ClinicianDecision(
        id=decision_id,
        assessment_id=assessment_id,
        decision_type="accepted",
        final_esi=3,
        decided_by_staff_id=nurse_id,
        reason_code="CLINICAL_REVIEW",
        decided_at=confirmed_at,
    )
    ward = Ward(
        id=ward_id,
        hospital_id=hospital_id,
        ward_code="ACUTE",
        name="Acute Care",
        ward_type="emergency",
        status="active",
    )
    doctor = Staff(
        id=doctor_id,
        hospital_id=hospital_id,
        employee_code="DOC-1",
        staff_type="doctor",
        first_name="Synthetic",
        employment_status="active",
        joined_on=confirmed_at.date(),
    )
    doctor_assignment = StaffWardAssignment(
        id=uuid4(),
        staff_id=doctor_id,
        ward_id=ward_id,
        role_in_ward="doctor",
        assigned_from=confirmed_at,
    )
    suggested_rule = EsiCareAreaRule(
        id=uuid4(),
        operational_config_id=assessment.operational_config_id,
        esi_level=3,
        ward_id=ward_id,
        priority=1,
        is_default=True,
    )
    current_doctor_work = (
        DoctorWorkItem(
            id=uuid4(),
            hospital_id=hospital_id,
            encounter_id=uuid4(),
            doctor_staff_id=doctor_id,
            ward_id=ward_id,
            status="in_service",
            priority_esi=2,
            queued_at=confirmed_at,
            started_at=confirmed_at,
            assigned_by_staff_id=nurse_id,
            allocation_reason="Existing synthetic patient",
            allocation_overview="Existing patient is currently with this doctor.",
            allocation_overview_factors={"doctor_was_busy": True},
        )
        if doctor_busy
        else None
    )

    session = MagicMock()
    session.scalar = AsyncMock(
        side_effect=[
            encounter,
            queue_entry,
            assessment,
            decision,
            ward,
            doctor,
            doctor_assignment,
            current_doctor_work,
            suggested_rule,
            None,
            *([1] if doctor_busy else []),
        ]
    )
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    service = EncounterService(session)
    service.participants.active_primary_doctor = AsyncMock(return_value=None)

    async def assign_generated_ids():
        for call in session.add.call_args_list:
            instance = call.args[0]
            if getattr(instance, "id", None) is None:
                instance.id = uuid4()

    session.flush.side_effect = assign_generated_ids
    payload = EncounterAllocationCreate(
        ward_id=ward_id,
        doctor_staff_id=doctor_id,
        confirmed_at=confirmed_at,
        bed_label="B-12",
        reason="Nurse confirmed allocation after triage review",
    )
    response = await service.confirm_allocation(
        encounter_id,
        payload,
        confirmed_by_staff_id=nurse_id,
        actor_auth_user_id=uuid4(),
        hospital_id=hospital_id,
        request_id="request-test",
    )

    added = [call.args[0] for call in session.add.call_args_list]
    location = next(item for item in added if isinstance(item, EncounterLocationHistory))
    participant = next(item for item in added if isinstance(item, EncounterParticipant))
    work_item = next(item for item in added if isinstance(item, DoctorWorkItem))
    audit = next(item for item in added if isinstance(item, AuditEvent))
    assert encounter.current_ward_id == ward_id
    assert (location.ward_id, location.moved_by_staff_id, location.bed_label) == (ward_id, nurse_id, "B-12")
    assert (participant.staff_id, participant.role, participant.assigned_by_staff_id) == (
        doctor_id,
        "primary_doctor",
        nurse_id,
    )
    assert audit.action == "encounter.allocation_confirmed"
    assert audit.event_metadata["clinician_decision_id"] == str(decision_id)
    expected_work_status = "waiting" if doctor_busy else "in_service"
    assert (work_item.status, work_item.doctor_staff_id, work_item.priority_esi) == (
        expected_work_status,
        doctor_id,
        3,
    )
    assert (queue_entry.status, queue_entry.exit_reason, queue_entry.exited_at) == (
        "completed",
        "allocated_to_doctor",
        confirmed_at,
    )
    assert response["location_history_id"] == location.id
    assert response["doctor_participant_id"] == participant.id
    assert response["doctor_work_item_id"] == work_item.id
    assert response["doctor_queue_position"] == (1 if doctor_busy else None)
    assert response["ai_overview"] == assessment.ai_overview
    assert response["allocation_overview"] == work_item.allocation_overview
    assert doctor.first_name in work_item.allocation_overview
    assert work_item.allocation_overview_factors["doctor_was_busy"] is doctor_busy
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_allocation_is_blocked_until_latest_assessment_is_confirmed():
    now = datetime.now(UTC)
    hospital_id = uuid4()
    encounter = Encounter(
        id=uuid4(),
        hospital_id=hospital_id,
        patient_id=uuid4(),
        encounter_code="ENC-PENDING",
        arrived_at=now,
        chief_complaint="Synthetic test complaint",
        status="arrived",
    )
    pending = TriageAssessment(
        id=uuid4(),
        encounter_id=encounter.id,
        assessment_number=1,
        operational_config_id=uuid4(),
        assessment_status="pending_confirmation",
        proposed_esi=3,
        recommended_esi=3,
        possible_esi_levels=[3],
        uncertainty_label="high_confidence",
        ai_overview="Pending test recommendation.",
        ai_overview_factors={"recommended_esi": 3},
        input_snapshot={},
        input_hash="0" * 64,
        score_source="test",
        engine_version="test",
    )
    queue_entry = QueueEntry(
        id=uuid4(), queue_id=uuid4(), encounter_id=encounter.id, entered_at=now, status="waiting"
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[encounter, queue_entry, pending, None])
    session.commit = AsyncMock()
    service = EncounterService(session)
    payload = EncounterAllocationCreate(
        ward_id=uuid4(), doctor_staff_id=uuid4(), confirmed_at=now, reason="Pending test allocation"
    )

    with pytest.raises(HTTPException, match="latest triage assessment must be clinician-confirmed") as raised:
        await service.confirm_allocation(
            encounter.id,
            payload,
            confirmed_by_staff_id=uuid4(),
            actor_auth_user_id=uuid4(),
            hospital_id=hospital_id,
            request_id="request-pending",
        )
    assert raised.value.status_code == 409
    session.commit.assert_not_awaited()
