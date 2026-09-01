from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.hospital import HospitalCreate, HospitalResponse, OperationalConfigCreate, WardCreate, WardResponse
from src.services.hospital_service import HospitalService

router = APIRouter(prefix="/hospitals", tags=["hospitals"])
Admin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.post("", response_model=HospitalResponse, status_code=status.HTTP_201_CREATED)
async def create_hospital(payload: HospitalCreate, session: DatabaseSession, _context: Admin):
    return await HospitalService(session).create_hospital(payload)


@router.get("/{hospital_id}", response_model=HospitalResponse)
async def get_hospital(hospital_id: UUID, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).get_hospital(hospital_id)


@router.post("/{hospital_id}/wards", response_model=WardResponse, status_code=status.HTTP_201_CREATED)
async def create_ward(hospital_id: UUID, payload: WardCreate, session: DatabaseSession, context: Admin):
    enforce_hospital_access(context, hospital_id)
    if payload.hospital_id != hospital_id:
        from fastapi import HTTPException

        raise HTTPException(422, "hospital_id in path and payload must match")
    return await HospitalService(session).create_ward(payload)


@router.post("/{hospital_id}/operational-configs", status_code=status.HTTP_201_CREATED)
async def create_operational_config(
    hospital_id: UUID, payload: OperationalConfigCreate, session: DatabaseSession, context: Admin
):
    enforce_hospital_access(context, hospital_id)
    return await HospitalService(session).create_operational_config(hospital_id, payload, context.staff_id)
