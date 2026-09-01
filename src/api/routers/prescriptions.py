from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.prescription import PrescriptionCancel, PrescriptionCreate, PrescriptionDraftUpdate, PrescriptionIssue
from src.services.prescription_service import PrescriptionService

router = APIRouter(tags=["prescriptions"])
Doctor = Annotated[RequestContext, Depends(require_roles("doctor"))]


@router.post("/encounters/{encounter_id}/prescriptions", status_code=status.HTTP_201_CREATED)
async def create_prescription(
    encounter_id: UUID, payload: PrescriptionCreate, session: DatabaseSession, context: Doctor
):
    if context.staff_id is None or context.hospital_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff hospital identity is required")
    return await PrescriptionService(session).create(encounter_id, payload, context.staff_id, context.hospital_id)


def _hospital_id(context: RequestContext) -> UUID:
    if context.hospital_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return context.hospital_id


@router.get("/encounters/{encounter_id}/prescriptions")
async def list_prescriptions(encounter_id: UUID, session: DatabaseSession, context: Doctor):
    return await PrescriptionService(session).list_for_encounter(encounter_id, _hospital_id(context))


@router.get("/prescriptions/{prescription_id}")
async def get_prescription(prescription_id: UUID, session: DatabaseSession, context: Doctor):
    return await PrescriptionService(session).detail(prescription_id, _hospital_id(context))


@router.patch("/prescriptions/{prescription_id}/draft")
async def update_prescription_draft(
    prescription_id: UUID, payload: PrescriptionDraftUpdate, session: DatabaseSession, context: Doctor
):
    return await PrescriptionService(session).update_draft(prescription_id, payload, _hospital_id(context))


@router.post("/prescriptions/{prescription_id}/issue")
async def issue_prescription(
    prescription_id: UUID, payload: PrescriptionIssue, session: DatabaseSession, context: Doctor
):
    return await PrescriptionService(session).issue(prescription_id, payload, _hospital_id(context))


@router.post("/prescriptions/{prescription_id}/cancel")
async def cancel_prescription(
    prescription_id: UUID, payload: PrescriptionCancel, session: DatabaseSession, context: Doctor
):
    return await PrescriptionService(session).cancel(prescription_id, payload, _hospital_id(context))
