"""Read-only audit-event discovery."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.services.audit_service import AuditService

router = APIRouter(prefix="/audit-events", tags=["audit"])
Auditor = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


@router.get("")
async def list_audit_events(
    session: DatabaseSession,
    context: Auditor,
    resource_type: str | None = None,
    resource_id: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
):
    return await AuditService(session).list(
        hospital_id=context.hospital_id,
        is_platform_admin=context.platform_role == "platform_admin",
        resource_type=resource_type,
        resource_id=resource_id,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}")
async def get_audit_event(event_id: UUID, session: DatabaseSession, context: Auditor):
    return await AuditService(session).get(
        event_id,
        context.hospital_id,
        is_platform_admin=context.platform_role == "platform_admin",
    )
