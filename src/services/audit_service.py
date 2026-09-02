"""Database-backed audit recording."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit import AuditEvent


async def record_audit_event(
    session: AsyncSession,
    *,
    hospital_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None,
    request_id: str,
    actor_staff_id: UUID | None = None,
    actor_auth_user_id: UUID | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        hospital_id=hospital_id,
        actor_auth_user_id=actor_auth_user_id,
        actor_staff_id=actor_staff_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        request_id=request_id,
        event_metadata=metadata or {},
        occurred_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(
        self,
        *,
        hospital_id: UUID | None,
        is_platform_admin: bool,
        resource_type: str | None,
        resource_id: UUID | None,
        page: int,
        page_size: int,
    ) -> dict:
        statement = select(AuditEvent)
        count_statement = select(func.count()).select_from(AuditEvent)
        if not is_platform_admin:
            if hospital_id is None:
                raise HTTPException(403, "hospital identity is required")
            statement = statement.where(AuditEvent.hospital_id == hospital_id)
            count_statement = count_statement.where(AuditEvent.hospital_id == hospital_id)
        if resource_type:
            statement = statement.where(AuditEvent.resource_type == resource_type)
            count_statement = count_statement.where(AuditEvent.resource_type == resource_type)
        if resource_id:
            statement = statement.where(AuditEvent.resource_id == resource_id)
            count_statement = count_statement.where(AuditEvent.resource_id == resource_id)
        total = await self.session.scalar(count_statement) or 0
        items = list(
            (
                await self.session.scalars(
                    statement.order_by(AuditEvent.occurred_at.desc()).limit(page_size).offset((page - 1) * page_size)
                )
            ).all()
        )
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "has_next": page * page_size < total,
        }

    async def get(self, event_id: UUID, hospital_id: UUID | None, *, is_platform_admin: bool) -> AuditEvent:
        event = await self.session.get(AuditEvent, event_id)
        if event is None:
            raise HTTPException(404, "audit event not found")
        if not is_platform_admin and event.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        return event
