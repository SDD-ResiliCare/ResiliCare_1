from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import DatabaseSession, RequestContext, require_roles
from src.schemas.feedback import (
    FeedbackCreate,
    FeedbackStatusUpdate,
    ReviewCreate,
    ReviewModerationUpdate,
    ReviewSubmission,
)
from src.services.feedback_service import FeedbackService

router = APIRouter(prefix="/feedback", tags=["feedback"])
Staff = Annotated[RequestContext, Depends(require_roles("administrator", "doctor", "nurse"))]
FeedbackAdmin = Annotated[RequestContext, Depends(require_roles("platform_admin", "administrator"))]


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


def _hospital_id(context: RequestContext) -> UUID:
    if context.hospital_id is None:
        raise HTTPException(403, "staff hospital identity is required")
    return context.hospital_id


@router.get("/reviews")
async def list_reviews(session: DatabaseSession, context: FeedbackAdmin):
    return await FeedbackService(session).list_reviews(_hospital_id(context))


@router.get("/reviews/{review_id}")
async def get_review(review_id: UUID, session: DatabaseSession, context: FeedbackAdmin):
    return await FeedbackService(session).get_review(review_id, _hospital_id(context))


@router.patch("/reviews/{review_id}/moderation")
async def moderate_review(
    review_id: UUID, payload: ReviewModerationUpdate, session: DatabaseSession, context: FeedbackAdmin
):
    return await FeedbackService(session).moderate_review(review_id, payload, _hospital_id(context))


@router.get("")
async def list_feedback(session: DatabaseSession, context: FeedbackAdmin):
    return await FeedbackService(session).list_feedback(_hospital_id(context))


@router.get("/{feedback_id}")
async def get_feedback(feedback_id: UUID, session: DatabaseSession, context: FeedbackAdmin):
    return await FeedbackService(session).get_feedback(feedback_id, _hospital_id(context))


@router.patch("/{feedback_id}")
async def update_feedback(
    feedback_id: UUID, payload: FeedbackStatusUpdate, session: DatabaseSession, context: FeedbackAdmin
):
    return await FeedbackService(session).update_feedback(feedback_id, payload, _hospital_id(context))
