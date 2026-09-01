"""Database-backed audit recording."""

from datetime import UTC, datetime
from uuid import UUID

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
