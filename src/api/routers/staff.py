from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.staff import StaffCreate, StaffResponse, WardAssignmentCreate
from src.services.staff_service import StaffService

router = APIRouter(prefix="/staff", tags=["staff"])
Admin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(payload: StaffCreate, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, payload.hospital_id)
    return await StaffService(session).create(payload)


@router.post("/{staff_id}/ward-assignments", status_code=status.HTTP_201_CREATED)
async def assign_ward(staff_id: UUID, payload: WardAssignmentCreate, session: DatabaseSession, context: Admin):
    service = StaffService(session)
    member = await service.get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.assign_ward(staff_id, payload, context.staff_id)
