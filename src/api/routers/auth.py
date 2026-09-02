from fastapi import APIRouter

from src.api.dependencies import CurrentContext

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me")
async def me(context: CurrentContext) -> dict:
    return {
        "auth_user_id": context.auth_user_id,
        "staff_id": context.staff_id,
        "hospital_id": context.hospital_id,
        "staff_type": context.staff_type,
        "platform_role": context.platform_role,
        "patient_ids": context.patient_ids,
    }
