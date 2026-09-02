from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import CurrentContext, DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.common import Page
from src.schemas.patient import (
    PatientAccessLinkCreate,
    PatientAllergyCreate,
    PatientConditionCreate,
    PatientCreate,
    PatientIdentifierCreate,
    PatientResponse,
    PatientUpdate,
)
from src.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]
PatientAdmin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await PatientService(session).create(payload, context.hospital_id)


@router.get("", response_model=Page[PatientResponse])
async def list_patients(
    session: DatabaseSession,
    context: ClinicalStaff,
    query: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    items, total = await PatientService(session).list_for_hospital(
        context.hospital_id, query=query, page=page, page_size=page_size
    )
    return Page(items=items, page=page, page_size=page_size, total=total, has_next=page * page_size < total)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    return await PatientService(session).get_for_hospital(patient_id, context.hospital_id)


@router.patch("/{patient_id}", response_model=PatientResponse)
async def update_patient(patient_id: UUID, payload: PatientUpdate, session: DatabaseSession, context: ClinicalStaff):
    service = PatientService(session)
    await service.get_for_hospital(patient_id, context.hospital_id)
    return await service.update(patient_id, payload)


@router.delete("/{patient_id}", response_model=PatientResponse)
async def archive_patient(patient_id: UUID, session: DatabaseSession, context: PatientAdmin):
    service = PatientService(session)
    await service.get_for_hospital(patient_id, context.hospital_id)
    return await service.archive(patient_id)


@router.post("/{patient_id}/identifiers", status_code=status.HTTP_201_CREATED)
async def add_identifier(
    patient_id: UUID, payload: PatientIdentifierCreate, session: DatabaseSession, context: ClinicalStaff
):
    enforce_hospital_access(context, payload.hospital_id)
    return await PatientService(session).add_identifier(patient_id, payload)


@router.post("/{patient_id}/allergies", status_code=status.HTTP_201_CREATED)
async def add_allergy(
    patient_id: UUID, payload: PatientAllergyCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff identity is required")
    await PatientService(session).get_for_hospital(patient_id, context.hospital_id)
    return await PatientService(session).add_allergy(patient_id, payload, context.staff_id)


@router.get("/{patient_id}/allergies")
async def list_allergies(patient_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    service = PatientService(session)
    await service.get_for_hospital(patient_id, context.hospital_id)
    return await service.list_allergies(patient_id)


@router.post("/{patient_id}/conditions", status_code=status.HTTP_201_CREATED)
async def add_condition(
    patient_id: UUID, payload: PatientConditionCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff identity is required")
    await PatientService(session).get_for_hospital(patient_id, context.hospital_id)
    return await PatientService(session).add_condition(patient_id, payload, context.staff_id)


@router.get("/{patient_id}/conditions")
async def list_conditions(patient_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    service = PatientService(session)
    await service.get_for_hospital(patient_id, context.hospital_id)
    return await service.list_conditions(patient_id)


@router.post("/{patient_id}/access-links", status_code=status.HTTP_201_CREATED)
async def grant_portal_access(
    patient_id: UUID, payload: PatientAccessLinkCreate, session: DatabaseSession, context: PatientAdmin
):
    await PatientService(session).get_for_hospital(patient_id, context.hospital_id)
    return await PatientService(session).grant_portal_access(patient_id, payload)


@router.get("/{patient_id}/portal-summary")
async def portal_summary(patient_id: UUID, session: DatabaseSession, context: CurrentContext):
    if patient_id not in context.patient_ids:
        from fastapi import HTTPException

        raise HTTPException(403, "patient portal access is not granted")
    return await PatientService(session).portal_summary(patient_id)
