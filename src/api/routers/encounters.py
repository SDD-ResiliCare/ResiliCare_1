from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.encounter import (
    DoctorTransferCreate,
    EncounterClosureCreate,
    EncounterCreate,
    EncounterDiagnosisCreate,
    EncounterResponse,
    ParticipantCreate,
    VitalObservationCreate,
)
from src.schemas.triage import SymptomInterviewCreate, SymptomResponseCreate
from src.services.encounter_service import EncounterService
from src.services.routing_service import RoutingService

router = APIRouter(prefix="/encounters", tags=["encounters"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]


@router.post("", response_model=EncounterResponse, status_code=status.HTTP_201_CREATED)
async def create_encounter(payload: EncounterCreate, session: DatabaseSession, context: ClinicalStaff):
    enforce_hospital_access(context, payload.hospital_id)
    return await EncounterService(session).create(payload)


@router.get("/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    encounter = await EncounterService(session).get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return encounter


@router.post("/{encounter_id}/participants", status_code=status.HTTP_201_CREATED)
async def add_participant(
    encounter_id: UUID, payload: ParticipantCreate, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.add_participant(encounter_id, payload, context.staff_id)


@router.post("/{encounter_id}/doctor-transfer", status_code=status.HTTP_201_CREATED)
async def transfer_doctor(
    encounter_id: UUID, payload: DoctorTransferCreate, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.transfer_doctor(encounter_id, payload, context.staff_id)


@router.post("/{encounter_id}/vitals", status_code=status.HTTP_201_CREATED)
async def record_vitals(
    encounter_id: UUID, payload: VitalObservationCreate, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.record_vitals(encounter_id, payload)


@router.post("/{encounter_id}/symptom-interviews", status_code=status.HTTP_201_CREATED)
async def start_interview(
    encounter_id: UUID, payload: SymptomInterviewCreate, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.start_interview(encounter_id, payload)


@router.post("/symptom-interviews/{interview_id}/responses", status_code=status.HTTP_201_CREATED)
async def record_response(
    interview_id: UUID, payload: SymptomResponseCreate, session: DatabaseSession, context: ClinicalStaff
):
    return await EncounterService(session).record_response(interview_id, payload, context.hospital_id)


@router.post("/{encounter_id}/diagnoses", status_code=status.HTTP_201_CREATED)
async def add_diagnosis(
    encounter_id: UUID, payload: EncounterDiagnosisCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff identity is required")
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.add_diagnosis(encounter_id, payload, context.staff_id)


@router.post("/{encounter_id}/closure", status_code=status.HTTP_201_CREATED)
async def close_encounter(
    encounter_id: UUID, payload: EncounterClosureCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff identity is required")
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.close_encounter(encounter_id, payload, context.staff_id)


@router.post("/{encounter_id}/routing-recommendations", status_code=status.HTTP_201_CREATED)
async def create_routing_recommendation(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff hospital identity is required")
    return await RoutingService(session).create_recommendation(encounter_id, context.hospital_id)
