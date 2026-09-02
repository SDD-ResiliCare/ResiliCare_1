from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import select

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.db.models.encounter import EncounterParticipant, RoutingRecommendation
from src.db.models.triage import (
    EncounterClosure,
    EncounterDiagnosis,
    SymptomInterview,
    SymptomResponse,
    VitalObservation,
)
from src.schemas.common import Page, ReasonAction
from src.schemas.encounter import (
    DoctorTransferCreate,
    EncounterAllocationCreate,
    EncounterAllocationResponse,
    EncounterClosureCreate,
    EncounterCreate,
    EncounterDiagnosisCreate,
    EncounterResponse,
    EncounterUpdate,
    ParticipantCreate,
    VitalObservationCreate,
)
from src.schemas.triage import SymptomInterviewCreate, SymptomResponseCreate
from src.services.encounter_service import EncounterService
from src.services.routing_service import RoutingService

router = APIRouter(prefix="/encounters", tags=["encounters"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]
Nurse = Annotated[RequestContext, Depends(require_roles("nurse"))]


@router.post("", response_model=EncounterResponse, status_code=status.HTTP_201_CREATED)
async def create_encounter(payload: EncounterCreate, session: DatabaseSession, context: ClinicalStaff):
    enforce_hospital_access(context, payload.hospital_id)
    return await EncounterService(session).create(payload)


@router.get("", response_model=Page[EncounterResponse])
async def list_encounters(
    session: DatabaseSession,
    context: ClinicalStaff,
    encounter_status: str | None = Query(default=None, alias="status"),
    patient_id: UUID | None = None,
    doctor_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    items, total = await EncounterService(session).list(
        context.hospital_id,
        status=encounter_status,
        patient_id=patient_id,
        doctor_id=doctor_id,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total, has_next=page * page_size < total)


@router.get("/{encounter_id}", response_model=EncounterResponse)
async def get_encounter(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    encounter = await EncounterService(session).get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return encounter


@router.patch("/{encounter_id}", response_model=EncounterResponse)
async def update_encounter(
    encounter_id: UUID, payload: EncounterUpdate, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.update(encounter_id, payload)


@router.delete("/{encounter_id}", response_model=EncounterResponse)
async def mark_encounter_entered_in_error(
    encounter_id: UUID, payload: ReasonAction, session: DatabaseSession, context: ClinicalStaff
):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.mark_entered_in_error(encounter_id, payload.reason)


@router.get("/{encounter_id}/workspace")
async def encounter_workspace(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    service = EncounterService(session)
    encounter = await service.get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return await service.workspace(encounter_id)


@router.post(
    "/{encounter_id}/allocation",
    response_model=EncounterAllocationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_encounter_allocation(
    encounter_id: UUID,
    payload: EncounterAllocationCreate,
    session: DatabaseSession,
    context: Nurse,
    request_id: Annotated[str | None, Header(alias="X-Request-ID", max_length=100)] = None,
):
    if context.staff_id is None or context.hospital_id is None:
        raise HTTPException(403, "nurse hospital identity is required")
    return await EncounterService(session).confirm_allocation(
        encounter_id,
        payload,
        confirmed_by_staff_id=context.staff_id,
        actor_auth_user_id=context.auth_user_id,
        hospital_id=context.hospital_id,
        request_id=request_id or str(uuid4()),
    )


async def _authorized_encounter(encounter_id: UUID, session: DatabaseSession, context: RequestContext):
    encounter = await EncounterService(session).get(encounter_id)
    enforce_hospital_access(context, encounter.hospital_id)
    return encounter


@router.get("/{encounter_id}/participants")
async def list_participants(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    return list(
        (
            await session.scalars(select(EncounterParticipant).where(EncounterParticipant.encounter_id == encounter_id))
        ).all()
    )


@router.get("/{encounter_id}/vitals")
async def list_vitals(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    return list(
        (
            await session.scalars(
                select(VitalObservation)
                .where(VitalObservation.encounter_id == encounter_id)
                .order_by(VitalObservation.observed_at.desc())
            )
        ).all()
    )


@router.get("/{encounter_id}/symptom-interviews")
async def list_symptom_interviews(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    return list(
        (
            await session.scalars(
                select(SymptomInterview)
                .where(SymptomInterview.encounter_id == encounter_id)
                .order_by(SymptomInterview.interview_number)
            )
        ).all()
    )


@router.get("/symptom-interviews/{interview_id}/responses")
async def list_symptom_responses(interview_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    interview = await session.get(SymptomInterview, interview_id)
    if interview is None:
        raise HTTPException(404, "symptom interview not found")
    await _authorized_encounter(interview.encounter_id, session, context)
    return list(
        (
            await session.scalars(
                select(SymptomResponse)
                .where(SymptomResponse.interview_id == interview_id)
                .order_by(SymptomResponse.answered_at)
            )
        ).all()
    )


@router.get("/{encounter_id}/diagnoses")
async def list_diagnoses(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    return list(
        (await session.scalars(select(EncounterDiagnosis).where(EncounterDiagnosis.encounter_id == encounter_id))).all()
    )


@router.get("/{encounter_id}/closure")
async def get_closure(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    closure = await session.scalar(select(EncounterClosure).where(EncounterClosure.encounter_id == encounter_id))
    if closure is None:
        raise HTTPException(404, "encounter closure not found")
    return closure


@router.get("/{encounter_id}/routing-recommendations")
async def list_routing_recommendations(encounter_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    await _authorized_encounter(encounter_id, session, context)
    return list(
        (
            await session.scalars(
                select(RoutingRecommendation).where(RoutingRecommendation.encounter_id == encounter_id)
            )
        ).all()
    )


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
