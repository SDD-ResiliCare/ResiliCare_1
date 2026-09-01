from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterParticipant
from src.db.models.triage import (
    EncounterClosure,
    EncounterDiagnosis,
    SymptomInterview,
    SymptomResponse,
    VitalObservation,
)
from src.db.repositories.encounters import (
    EncounterParticipantRepository,
    EncounterRepository,
    SymptomInterviewRepository,
    SymptomResponseRepository,
    VitalObservationRepository,
)
from src.schemas.encounter import (
    DoctorTransferCreate,
    EncounterClosureCreate,
    EncounterCreate,
    EncounterDiagnosisCreate,
    ParticipantCreate,
    VitalObservationCreate,
)
from src.schemas.triage import SymptomInterviewCreate, SymptomResponseCreate


class EncounterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.encounters = EncounterRepository(session)
        self.participants = EncounterParticipantRepository(session)
        self.vitals = VitalObservationRepository(session)
        self.interviews = SymptomInterviewRepository(session)
        self.responses = SymptomResponseRepository(session)

    async def create(self, payload: EncounterCreate) -> Encounter:
        encounter = await self.encounters.add(Encounter(**payload.model_dump(), status="arrived"))
        await self.session.commit()
        return encounter

    async def get(self, encounter_id: UUID, *, for_update: bool = False) -> Encounter:
        encounter = await self.encounters.get(encounter_id, for_update=for_update)
        if encounter is None:
            raise HTTPException(404, "encounter not found")
        return encounter

    async def add_participant(
        self, encounter_id: UUID, payload: ParticipantCreate, assigned_by: UUID | None
    ) -> EncounterParticipant:
        await self.get(encounter_id)
        if payload.role == "primary_doctor" and await self.participants.active_primary_doctor(encounter_id):
            raise HTTPException(409, "encounter already has an active primary doctor; use doctor transfer")
        participant = await self.participants.add(
            EncounterParticipant(
                encounter_id=encounter_id,
                assigned_by_staff_id=assigned_by,
                **payload.model_dump(),
            )
        )
        await self.session.commit()
        return participant

    async def transfer_doctor(
        self, encounter_id: UUID, payload: DoctorTransferCreate, assigned_by: UUID | None
    ) -> EncounterParticipant:
        await self.get(encounter_id, for_update=True)
        current = await self.participants.active_primary_doctor(encounter_id, for_update=True)
        if current is None:
            raise HTTPException(409, "encounter has no active primary doctor")
        if current.staff_id == payload.new_doctor_staff_id:
            raise HTTPException(409, "new doctor is already the active primary doctor")
        current.ended_at = payload.transferred_at
        current.end_reason = payload.reason
        replacement = await self.participants.add(
            EncounterParticipant(
                encounter_id=encounter_id,
                staff_id=payload.new_doctor_staff_id,
                role="primary_doctor",
                assigned_at=payload.transferred_at,
                assigned_by_staff_id=assigned_by,
                assignment_reason=payload.reason,
                transferred_from_participant_id=current.id,
            )
        )
        await self.session.commit()
        return replacement

    async def record_vitals(self, encounter_id: UUID, payload: VitalObservationCreate) -> VitalObservation:
        await self.get(encounter_id)
        values = payload.model_dump()
        components = (payload.gcs_eye, payload.gcs_verbal, payload.gcs_motor)
        values["gcs_total"] = sum(components) if all(value is not None for value in components) else None
        observation = await self.vitals.add(VitalObservation(encounter_id=encounter_id, **values))
        await self.session.commit()
        return observation

    async def start_interview(self, encounter_id: UUID, payload: SymptomInterviewCreate) -> SymptomInterview:
        await self.get(encounter_id)
        next_number = (
            await self.session.scalar(
                select(func.coalesce(func.max(SymptomInterview.interview_number), 0) + 1).where(
                    SymptomInterview.encounter_id == encounter_id
                )
            )
        ) or 1
        interview = await self.interviews.add(
            SymptomInterview(
                encounter_id=encounter_id,
                interview_number=next_number,
                status="in_progress",
                **payload.model_dump(),
            )
        )
        await self.session.commit()
        return interview

    async def record_response(
        self, interview_id: UUID, payload: SymptomResponseCreate, hospital_id: UUID | None
    ) -> SymptomResponse:
        interview = await self.interviews.get(interview_id)
        if interview is None:
            raise HTTPException(404, "symptom interview not found")
        encounter = await self.get(interview.encounter_id)
        if hospital_id is not None and encounter.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        if interview.status != "in_progress":
            raise HTTPException(409, "symptom interview is not open")
        response = await self.responses.add(SymptomResponse(interview_id=interview_id, **payload.model_dump()))
        await self.session.commit()
        return response

    async def add_diagnosis(
        self, encounter_id: UUID, payload: EncounterDiagnosisCreate, staff_id: UUID
    ) -> EncounterDiagnosis:
        await self.get(encounter_id)
        diagnosis = EncounterDiagnosis(
            encounter_id=encounter_id, diagnosed_by_staff_id=staff_id, **payload.model_dump()
        )
        self.session.add(diagnosis)
        await self.session.commit()
        await self.session.refresh(diagnosis)
        return diagnosis

    async def close_encounter(
        self, encounter_id: UUID, payload: EncounterClosureCreate, staff_id: UUID
    ) -> EncounterClosure:
        encounter = await self.get(encounter_id, for_update=True)
        if encounter.completed_at is not None:
            raise HTTPException(409, "encounter is already closed")
        closure = EncounterClosure(encounter_id=encounter_id, closed_by_staff_id=staff_id, **payload.model_dump())
        self.session.add(closure)
        encounter.status = "completed"
        encounter.completed_at = payload.closed_at
        await self.session.commit()
        await self.session.refresh(closure)
        return closure
