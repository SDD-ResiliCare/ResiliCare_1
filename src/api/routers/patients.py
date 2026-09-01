from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import CurrentContext, DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.patient import (
    PatientAccessLinkCreate,
    PatientAllergyCreate,
    PatientConditionCreate,
    PatientCreate,
    PatientIdentifierCreate,
    PatientResponse,
)
from src.services.patient_service import PatientService

router = APIRouter(prefix="/patients", tags=["patients"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]
PatientAdmin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(payload: PatientCreate, session: DatabaseSession, _context: ClinicalStaff):
    return await PatientService(session).create(payload)


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    return await PatientService(session).get_for_hospital(patient_id, context.hospital_id)


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


@router.post("/{patient_id}/conditions", status_code=status.HTTP_201_CREATED)
async def add_condition(
    patient_id: UUID, payload: PatientConditionCreate, session: DatabaseSession, context: ClinicalStaff
):
    if context.staff_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff identity is required")
    await PatientService(session).get_for_hospital(patient_id, context.hospital_id)
    return await PatientService(session).add_condition(patient_id, payload, context.staff_id)


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
