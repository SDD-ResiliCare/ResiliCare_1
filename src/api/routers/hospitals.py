from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.common import Page
from src.schemas.hospital import (
    HospitalCreate,
    HospitalResponse,
    HospitalUpdate,
    OperationalConfigCreate,
    WardCreate,
    WardResponse,
    WardUpdate,
)
from src.services.hospital_service import HospitalService

router = APIRouter(prefix="/hospitals", tags=["hospitals"])
Admin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]
ClinicalStaff = Annotated[
    RequestContext, Depends(require_roles("platform_admin", "administrator", "nurse", "receptionist", "doctor"))
]


@router.post("", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED)
async def create_hospital(payload: HospitalCreate, session: DatabaseSession, _context: Admin):
    if _context.platform_role != "platform_admin":
        raise HTTPException(403, "only platform administrators can create hospitals")
    return await HospitalService(session).create_hospital(payload)


@router.get("", response_model=Page[HospitalResponse])
async def list_hospitals(
    session: DatabaseSession,
    context: ClinicalStaff,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    if context.platform_role != "platform_admin":
        if context.hospital_id is None:
            raise HTTPException(403, "hospital identity is required")
        hospital = await HospitalService(session).get_hospital(context.hospital_id)
        return Page(items=[hospital], page=1, page_size=page_size, total=1, has_next=False)
    items, total = await HospitalService(session).list_hospitals(page=page, page_size=page_size)
    return Page(items=items, page=page, page_size=page_size, total=total, has_next=page * page_size < total)


@router.get("/current", response_model=HospitalResponse)
async def current_hospital(session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(404, "current user is not linked to a hospital")
    return await HospitalService(session).get_hospital(context.hospital_id)


@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(hospital_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).get_hospital(hospital_id)


@router.patch("/{hospital_id}", response_model=HospitalResponse)
async def update_hospital(hospital_id: UUID, payload: HospitalUpdate, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).update_hospital(hospital_id, payload)


@router.delete("/{hospital_id}", response_model=HospitalResponse)
async def deactivate_hospital(hospital_id: UUID, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).deactivate_hospital(hospital_id)


@router.get("/{hospital_id}/wards", response_model=Page[WardResponse])
async def list_wards(
    hospital_id: UUID,
    session: DatabaseSession,
    context: ClinicalStaff,
    include_inactive: bool = Query(default=False),
):
    enforce_hospital_access(context, hospital_id)
    wards = await HospitalService(session).list_wards(hospital_id, include_inactive=include_inactive)
    return Page(items=wards, page=1, page_size=len(wards) or 1, total=len(wards), has_next=False)


@router.post("/{hospital_id}/wards", response_model=WardResponse, status_code=status.HTTP_201_CREATED)
async def create_ward(hospital_id: UUID, payload: WardCreate, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    if payload.hospital_id != hospital_id:
        from fastapi import HTTPException

        raise HTTPException(422, "hospital_id in path and payload must match")
    return await HospitalService(session).create_ward(payload)


@router.get("/wards/{ward_id}", response_model=WardResponse)
async def get_ward(ward_id: UUID, session: DatabaseSession, context: Admin):
    ward = await HospitalService(session).get_ward(ward_id)
    enforce_hospital_access(context, ward.hospital_id)
    return ward


@router.patch("/wards/{ward_id}", response_model=WardResponse)
async def update_ward(ward_id: UUID, payload: WardUpdate, session: DatabaseSession, context: Admin):
    service = HospitalService(session)
    ward = await service.get_ward(ward_id)
    enforce_hospital_access(context, ward.hospital_id)
    return await service.update_ward(ward_id, payload)


@router.delete("/wards/{ward_id}", response_model=WardResponse)
async def deactivate_ward(ward_id: UUID, session: DatabaseSession, context: Admin):
    service = HospitalService(session)
    ward = await service.get_ward(ward_id)
    enforce_hospital_access(context, ward.hospital_id)
    return await service.deactivate_ward(ward_id)


@router.post("/{hospital_id}/operational-configs", status_code=status.HTTP_201_CREATED)
async def create_operational_config(
    hospital_id: UUID, payload: OperationalConfigCreate, session: DatabaseSession, context: Admin
):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).create_operational_config(hospital_id, payload, context.staff_id)


@router.get("/{hospital_id}/operational-configs")
async def list_operational_configs(hospital_id: UUID, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).list_operational_configs(hospital_id)
