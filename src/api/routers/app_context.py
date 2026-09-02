"""Frontend bootstrap context derived from the authenticated identity."""

from fastapi import APIRouter

from src.api.dependencies import CurrentContext, DatabaseSession
from src.services.app_context_service import AppContextService

router = APIRouter(tags=["application"])


@router.get("/app-context")
async def app_context(session: DatabaseSession, context: CurrentContext):
    return await AppContextService(session).build(
        auth_user_id=context.auth_user_id,
        platform_role=context.platform_role,
        staff_id=context.staff_id,
        hospital_id=context.hospital_id,
        staff_type=context.staff_type,
        patient_ids=context.patient_ids,
    )
