"""Verified reviews and operational feedback models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FeedbackInvite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback_invites"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    used_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reviews"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    review_target: Mapped[str] = mapped_column(String(20), nullable=False)
    reviewed_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    overall_rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    dimension_ratings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    would_recommend: Mapped[bool | None] = mapped_column(Boolean)
    review_text: Mapped[str | None] = mapped_column(Text)
    is_anonymous_publicly: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    moderation_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class FeedbackSubmission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feedback_submissions"

    encounter_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"))
    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    contact_permission: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="new")
    assigned_to_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
