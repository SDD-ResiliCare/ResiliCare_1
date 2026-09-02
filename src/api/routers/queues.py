from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, enforce_hospital_access, require_roles
from src.schemas.encounter import (
    CurrentQueueResponse,
    QueueCreate,
    QueueEntryAction,
    QueueEntryCreate,
    QueuePriorityUpdate,
    QueueUpdate,
)
from src.services.queue_service import QueueService

router = APIRouter(prefix="/queues", tags=["queues"])
ClinicalStaff = Annotated[RequestContext, Depends(require_roles("administrator", "nurse", "receptionist"))]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_queue(payload: QueueCreate, session: DatabaseSession, context: ClinicalStaff):
    enforce_hospital_access(context, payload.hospital_id)
    return await QueueService(session).create_queue(payload)


@router.get("")
async def list_queues(session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await QueueService(session).list_queues(context.hospital_id)


@router.get("/current")
async def current_queue(session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await QueueService(session).current_queue(context.hospital_id)


@router.get("/current/entries", response_model=CurrentQueueResponse)
async def current_queue_entries(session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    service = QueueService(session)
    queue = await service.current_queue(context.hospital_id)
    return {"queue": queue, "entries": await service.ranked_entries(queue)}


@router.post("/current/entries", status_code=status.HTTP_201_CREATED)
async def add_current_queue_entry(payload: QueueEntryCreate, session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    service = QueueService(session)
    queue = await service.current_queue(context.hospital_id)
    return await service.add_entry(queue.id, payload)


@router.patch("/entries/{entry_id}/priority")
async def update_queue_priority(
    entry_id: UUID, payload: QueuePriorityUpdate, session: DatabaseSession, context: ClinicalStaff
):
    if context.hospital_id is None or context.staff_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return await QueueService(session).update_priority(entry_id, payload, context.staff_id, context.hospital_id)


async def _transition(
    entry_id: UUID,
    action: str,
    payload: QueueEntryAction,
    session: DatabaseSession,
    context: RequestContext,
):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await QueueService(session).transition(entry_id, action, payload, context.hospital_id)


@router.post("/entries/{entry_id}/call")
async def call_queue_entry(entry_id: UUID, payload: QueueEntryAction, session: DatabaseSession, context: ClinicalStaff):
    return await _transition(entry_id, "call", payload, session, context)


@router.post("/entries/{entry_id}/start-care")
async def start_queue_entry_care(
    entry_id: UUID, payload: QueueEntryAction, session: DatabaseSession, context: ClinicalStaff
):
    return await _transition(entry_id, "start-care", payload, session, context)


@router.post("/entries/{entry_id}/exit")
async def exit_queue_entry(entry_id: UUID, payload: QueueEntryAction, session: DatabaseSession, context: ClinicalStaff):
    return await _transition(entry_id, "exit", payload, session, context)


@router.post("/entries/{entry_id}/cancel")
async def cancel_queue_entry(
    entry_id: UUID, payload: QueueEntryAction, session: DatabaseSession, context: ClinicalStaff
):
    return await _transition(entry_id, "cancel", payload, session, context)


@router.get("/{queue_id}")
async def get_queue(queue_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    queue = await QueueService(session).get_queue(queue_id)
    enforce_hospital_access(context, queue.hospital_id)
    return queue


@router.patch("/{queue_id}")
async def update_queue(queue_id: UUID, payload: QueueUpdate, session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await QueueService(session).update_queue(queue_id, payload, context.hospital_id)


@router.delete("/{queue_id}")
async def deactivate_queue(queue_id: UUID, session: DatabaseSession, context: ClinicalStaff):
    if context.hospital_id is None:
        raise HTTPException(403, "hospital identity is required")
    return await QueueService(session).deactivate_queue(queue_id, context.hospital_id)


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
