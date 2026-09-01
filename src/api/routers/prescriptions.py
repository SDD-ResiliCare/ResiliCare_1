from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.prescription import PrescriptionCreate
from src.services.prescription_service import PrescriptionService

router = APIRouter(prefix="/encounters", tags=["prescriptions"])
Doctor = Annotated[RequestContext, Depends(require_roles("doctor"))]


@router.post("/{encounter_id}/prescriptions", status_code=status.HTTP_201_CREATED)
async def create_prescription(
    encounter_id: UUID, payload: PrescriptionCreate, session: DatabaseSession, context: Doctor
):
    if context.staff_id is None or context.hospital_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff hospital identity is required")
    return await PrescriptionService(session).create(encounter_id, payload, context.staff_id, context.hospital_id)
