from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.common import Page
from src.schemas.staff import StaffCreate, StaffResponse, StaffUpdate, WardAssignmentCreate
from src.services.staff_service import StaffService

router = APIRouter(prefix="/staff", tags=["staff"])
Admin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]
ClinicalStaff = Annotated[
    RequestContext, Depends(require_roles("platform_admin", "administrator", "nurse", "receptionist", "doctor"))
]


@router.post("", response_model=StaffResponse, status_code=status.HTTP_201_CREATED)
async def create_staff(payload: StaffCreate, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, payload.hospital_id)
    return await StaffService(session).create(payload)


@router.get("", response_model=Page[StaffResponse])
async def list_staff(
    session: DatabaseSession,
    context: ClinicalStaff,
    query: str | None = None,
    staff_type: str | None = None,
    ward_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    items, total = await StaffService(session).list(
        context.hospital_id,
        query=query,
        staff_type=staff_type,
        ward_id=ward_id,
        page=page,
        page_size=page_size,
    )
    return Page(items=items, page=page, page_size=page_size, total=total, has_next=page * page_size < total)


@router.get("/{staff_id}", response_model=StaffResponse)
async def get_staff(staff_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    member = await StaffService(session).get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return member


@router.patch("/{staff_id}", response_model=StaffResponse)
async def update_staff(staff_id: UUID, payload: StaffUpdate, session: DatabaseSession, context: Admin):
    service = StaffService(session)
    member = await service.get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.update(staff_id, payload)


@router.delete("/{staff_id}", response_model=StaffResponse)
async def deactivate_staff(staff_id: UUID, session: DatabaseSession, context: Admin):
    service = StaffService(session)
    member = await service.get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.deactivate(staff_id)


@router.post("/{staff_id}/ward-assignments", status_code=status.HTTP_201_CREATED)
async def assign_ward(staff_id: UUID, payload: WardAssignmentCreate, session: DatabaseSession, context: Admin):
    service = StaffService(session)
    member = await service.get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.assign_ward(staff_id, payload, context.staff_id)


@router.get("/{staff_id}/ward-assignments")
async def list_ward_assignments(staff_id: UUID, session: DatabaseSession, context: Admin):
    service = StaffService(session)
    member = await service.get(staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.list_assignments(staff_id)


@router.delete("/ward-assignments/{assignment_id}")
async def end_ward_assignment(assignment_id: UUID, ended_at: datetime, session: DatabaseSession, context: Admin):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    service = StaffService(session)
    assignment = await service.assignments.get(assignment_id)
    if assignment is None:
        raise HTTPException(404, "ward assignment not found")
    member = await service.get(assignment.staff_id)
    enforce_hospital_access(context, member.hospital_id)
    return await service.end_assignment(assignment_id, ended_at)
