from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.feedback import FeedbackCreate, ReviewCreate, ReviewSubmission
from src.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])
Staff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]


@router.post("/encounters/{encounter_id}/invite", status_code=status.HTTP_201_CREATED)
async def create_invite(encounter_id: UUID, session: DatabaseSession, context: Staff):
    if context.hospital_id is None:
        from fastapi import HTTPException

        raise HTTPException(403, "staff hospital identity is required")
    invite, raw_token = await FeedbackService(session).create_invite(encounter_id, context.hospital_id)
    return {"invite_id": invite.id, "token": raw_token, "expires_at": invite.expires_at}


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
async def submit_review(payload: ReviewSubmission, session: DatabaseSession):
    review = ReviewCreate.model_validate(payload.model_dump(exclude={"token"}))
    return await FeedbackService(session).submit_review(payload.token, review)


@router.post("", status_code=status.HTTP_201_CREATED)
async def submit_feedback(payload: FeedbackCreate, session: DatabaseSession):
    return await FeedbackService(session).submit_feedback(payload)
