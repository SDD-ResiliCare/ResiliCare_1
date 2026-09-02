"""FastAPI dependencies for DB sessions and role-aware Supabase authentication."""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from anyio import to_thread
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.patient import PatientAccessLink
from src.db.models.workforce import Staff
from src.db.session import get_database_session
from src.integrations.supabase_auth import verify_access_token

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
bearer = HTTPBearer(auto_error=True)


@dataclass(frozen=True)
class RequestContext:
    auth_user_id: UUID
    platform_role: str | None
    staff_id: UUID | None
    hospital_id: UUID | None
    staff_type: str | None
    patient_ids: tuple[UUID, ...]


async def get_request_context(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)],
    session: DatabaseSession,
) -> RequestContext:
    try:
        claims = await to_thread.run_sync(verify_access_token, credentials.credentials)
        auth_user_id = UUID(claims["sub"])
    except Exception as exc:
        raise HTTPException(401, "invalid or expired access token") from exc
    member = await session.scalar(select(Staff).where(Staff.auth_user_id == auth_user_id))
    patient_ids = tuple(
        (
            await session.scalars(
                select(PatientAccessLink.patient_id).where(
                    PatientAccessLink.auth_user_id == auth_user_id,
                    PatientAccessLink.status == "active",
                    PatientAccessLink.revoked_at.is_(None),
                )
            )
        ).all()
    )
    app_metadata = claims.get("app_metadata") or {}
    return RequestContext(
        auth_user_id=auth_user_id,
        platform_role=app_metadata.get("role"),
        staff_id=member.id if member else None,
        hospital_id=member.hospital_id if member else None,
        staff_type=member.staff_type if member else None,
        patient_ids=patient_ids,
    )


CurrentContext = Annotated[RequestContext, Depends(get_request_context)]


def require_roles(*roles: str):
    async def dependency(context: CurrentContext) -> RequestContext:
        granted = {context.platform_role, context.staff_type}
        if not granted.intersection(roles):
            raise HTTPException(403, "insufficient role")
        return context

    return dependency


def enforce_hospital_access(context: RequestContext, hospital_id: UUID) -> None:
    if context.platform_role == "platform_admin":
        return
    if context.hospital_id != hospital_id:
        raise HTTPException(403, "cross-hospital access is not allowed")
