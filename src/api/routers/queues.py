from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.encounter import QueueCreate, QueueEntryCreate
from src.services.queue_service import QueueService

router = APIRouter(prefix="/queues", tags=["queues"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_queue(payload: QueueCreate, session: DatabaseSession, context: ClinicalStaff):
    enforce_hospital_access(context, payload.hospital_id)
    return await QueueService(session).create_queue(payload)


@router.get("/{queue_id}/entries")
async def list_entries(queue_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    service = QueueService(session)
    queue = await service.get_queue(queue_id)
    enforce_hospital_access(context, queue.hospital_id)
    return await service.list_entries(queue_id)


@router.post("/{queue_id}/entries", status_code=status.HTTP_201_CREATED)
async def add_entry(queue_id: UUID, payload: QueueEntryCreate, session: DatabaseSession, context: ClinicalStaff):
    service = QueueService(session)
    queue = await service.get_queue(queue_id)
    enforce_hospital_access(context, queue.hospital_id)
    return await service.add_entry(queue_id, payload)
