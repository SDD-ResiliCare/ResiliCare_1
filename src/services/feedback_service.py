import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterParticipant
from src.db.models.feedback import FeedbackInvite, FeedbackSubmission, Review
from src.db.repositories.feedback import FeedbackInviteRepository, FeedbackRepository, ReviewRepository
from src.schemas.feedback import FeedbackCreate, ReviewCreate


class FeedbackService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.invites = FeedbackInviteRepository(session)
        self.reviews = ReviewRepository(session)
        self.feedback = FeedbackRepository(session)

    async def create_invite(
        self, encounter_id: UUID, hospital_id: UUID, *, expires_in_days: int = 14
    ) -> tuple[FeedbackInvite, str]:
        encounter = await self.session.get(Encounter, encounter_id)
        if encounter is None:
            raise HTTPException(404, "encounter not found")
        if encounter.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        raw_token = secrets.token_urlsafe(32)
        invite = await self.invites.add(
            FeedbackInvite(
                encounter_id=encounter_id,
                token_hash=self._hash(raw_token),
                expires_at=datetime.now(UTC) + timedelta(days=expires_in_days),
                max_uses=3,
                used_count=0,
            )
        )
        await self.session.commit()
        return invite, raw_token

    async def submit_review(self, raw_token: str, payload: ReviewCreate) -> Review:
        invite = await self.session.scalar(
            select(FeedbackInvite).where(FeedbackInvite.token_hash == self._hash(raw_token)).with_for_update()
        )
        now = datetime.now(UTC)
        if (
            invite is None
            or invite.revoked_at is not None
            or invite.expires_at <= now
            or invite.used_count >= invite.max_uses
        ):
            raise HTTPException(404, "feedback invitation is invalid or expired")
        if payload.review_target == "doctor":
            assigned = await self.session.scalar(
                select(EncounterParticipant.id).where(
                    EncounterParticipant.encounter_id == invite.encounter_id,
                    EncounterParticipant.staff_id == payload.reviewed_staff_id,
                    EncounterParticipant.role == "primary_doctor",
                )
            )
            if assigned is None:
                raise HTTPException(422, "doctor was not assigned to this encounter")
        review = await self.reviews.add(
            Review(
                encounter_id=invite.encounter_id,
                moderation_status="pending",
                submitted_at=now,
                **payload.model_dump(),
            )
        )
        invite.used_count += 1
        await self.session.commit()
        return review

    async def submit_feedback(self, payload: FeedbackCreate) -> FeedbackSubmission:
        feedback = await self.feedback.add(FeedbackSubmission(**payload.model_dump(), status="new"))
        await self.session.commit()
        return feedback

    @staticmethod
    def _hash(raw_token: str) -> str:
        return hashlib.sha256(raw_token.encode()).hexdigest()
