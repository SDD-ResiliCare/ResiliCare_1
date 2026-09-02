from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import src.db.models  # noqa: F401
from src.db.base import Base
from src.db.models.encounter import DoctorWorkItem, Encounter
from src.db.models.organization import Ward
from src.db.models.patient import Patient
from src.db.models.workforce import Staff
from src.main import app
from src.services.app_context_service import ROLE_PERMISSIONS
from src.services.doctor_work_service import DoctorWorkService


def _doctor(hospital_id):
    return Staff(
        id=uuid4(),
        hospital_id=hospital_id,
        employee_code="DOC-WORK",
        staff_type="doctor",
        first_name="Synthetic",
        last_name="Doctor",
        employment_status="active",
        joined_on=datetime.now(UTC).date(),
    )


def _work_row(doctor, ward, status, queued_at, esi):
    patient = Patient(id=uuid4(), first_name="Synthetic", last_name=status.title(), estimated_age_years=30)
    encounter = Encounter(
        id=uuid4(),
        hospital_id=doctor.hospital_id,
        patient_id=patient.id,
        encounter_code=f"ENC-{status}-{esi}",
        arrived_at=queued_at,
        chief_complaint="Synthetic test complaint",
        status="in_care" if status == "in_service" else "assigned",
    )
    item = DoctorWorkItem(
        id=uuid4(),
        hospital_id=doctor.hospital_id,
        encounter_id=encounter.id,
        doctor_staff_id=doctor.id,
        ward_id=ward.id,
        status=status,
        priority_esi=esi,
        queued_at=queued_at,
        started_at=queued_at if status == "in_service" else None,
        assigned_by_staff_id=uuid4(),
        allocation_reason="Synthetic allocation",
    )
    return item, encounter, patient, ward


@pytest.mark.asyncio
async def test_workload_exposes_busy_doctor_current_patient_and_ordered_waiting_line():
    hospital_id = uuid4()
    doctor = _doctor(hospital_id)
    ward = Ward(
        id=uuid4(),
        hospital_id=hospital_id,
        ward_code="ACUTE",
        name="Acute Care",
        ward_type="emergency",
        status="active",
    )
    now = datetime.now(UTC)
    rows = [
        _work_row(doctor, ward, "in_service", now, 3),
        _work_row(doctor, ward, "waiting", now + timedelta(minutes=2), 2),
        _work_row(doctor, ward, "waiting", now + timedelta(minutes=4), 4),
    ]
    result = MagicMock()
    result.all.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    workload = await DoctorWorkService(session)._workload(doctor)

    assert workload["availability"] == "busy"
    assert workload["current_patient"]["status"] == "in_service"
    assert workload["waiting_count"] == 2
    assert [item["queue_position"] for item in workload["waiting_patients"]] == [1, 2]
    assert [item["confirmed_esi"] for item in workload["waiting_patients"]] == [2, 4]


@pytest.mark.asyncio
async def test_finishing_current_patient_promotes_next_waiting_patient():
    hospital_id = uuid4()
    doctor = _doctor(hospital_id)
    ward = Ward(
        id=uuid4(),
        hospital_id=hospital_id,
        ward_code="ACUTE",
        name="Acute Care",
        ward_type="emergency",
        status="active",
    )
    now = datetime.now(UTC)
    current, current_encounter, _patient, _ward = _work_row(doctor, ward, "in_service", now, 3)
    next_item, next_encounter, _patient, _ward = _work_row(
        doctor, ward, "waiting", now + timedelta(minutes=2), 2
    )
    session = MagicMock()
    session.scalar = AsyncMock(side_effect=[current, doctor, next_item])
    session.get = AsyncMock(return_value=next_encounter)
    completed_at = now + timedelta(minutes=30)

    completed, promoted = await DoctorWorkService(session).finish_encounter_work(
        current_encounter.id, completed_at, "Encounter closed"
    )

    assert completed is current
    assert (current.status, current.completed_at) == ("completed", completed_at)
    assert promoted is next_item
    assert (next_item.status, next_item.started_at) == ("in_service", completed_at)
    assert (next_encounter.status, next_encounter.care_started_at) == ("in_care", completed_at)


def test_doctor_work_queue_schema_and_frontend_routes_are_present():
    table = Base.metadata.tables["doctor_work_items"]
    indexes = {index.name: index for index in table.indexes}
    assert indexes["uq_doctor_work_items_current_doctor"].unique is True
    assert indexes["uq_doctor_work_items_active_encounter"].unique is True
    migration = (Path(__file__).parents[1] / "supabase" / "migrations" / "008_doctor_work_queue.sql").read_text(
        encoding="utf-8"
    )
    assert "create table doctor_work_items" in migration.lower()
    paths = app.openapi()["paths"]
    assert "/api/v1/staff/doctors/workloads" in paths
    assert "/api/v1/staff/doctors/{doctor_id}/workload" in paths
    assert "allocate_care_team" in ROLE_PERMISSIONS["receptionist"]
