"""Queue, encounter, participant, coverage, and routing models."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Queue(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "queues"
    __table_args__ = (UniqueConstraint("hospital_id", "queue_code"),)

    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    ward_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"))
    queue_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    queue_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class Encounter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounters"
    __table_args__ = (UniqueConstraint("hospital_id", "encounter_code"),)

    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    encounter_code: Mapped[str] = mapped_column(String(80), nullable=False)
    encounter_type: Mapped[str] = mapped_column(String(40), nullable=False, default="emergency")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="arrived")
    arrival_mode: Mapped[str | None] = mapped_column(String(40))
    arrived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    care_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_ward_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"))
    chief_complaint: Mapped[str] = mapped_column(Text, nullable=False)
    presenting_details: Mapped[str | None] = mapped_column(Text)
    symptom_onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    symptom_onset_precision: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    data_quality_notes: Mapped[str | None] = mapped_column(Text)


class QueueEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "queue_entries"
    __table_args__ = (
        Index(
            "uq_queue_entries_active_encounter", "encounter_id", unique=True, postgresql_where=text("exited_at IS NULL")
        ),
    )

    queue_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("queues.id"), nullable=False)
    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="waiting")
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority_boost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    priority_boost_reason: Mapped[str | None] = mapped_column(Text)
    priority_boost_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    boosted_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    reassessment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ranked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EncounterLocationHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounter_location_history"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    ward_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"), nullable=False)
    bed_label: Mapped[str | None] = mapped_column(String(50))
    entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    transfer_reason: Mapped[str | None] = mapped_column(Text)
    moved_by_staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)


class EncounterParticipant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounter_participants"
    __table_args__ = (
        Index(
            "uq_encounter_active_primary_doctor",
            "encounter_id",
            unique=True,
            postgresql_where=text("role = 'primary_doctor' AND ended_at IS NULL"),
        ),
    )

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    assignment_reason: Mapped[str | None] = mapped_column(Text)
    end_reason: Mapped[str | None] = mapped_column(Text)
    transferred_from_participant_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("encounter_participants.id")
    )


class EncounterCoverage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounter_coverages"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    scheme_code: Mapped[str] = mapped_column(String(80), nullable=False)
    payer_name: Mapped[str | None] = mapped_column(String(200))
    member_reference: Mapped[str | None] = mapped_column(String(120))
    coverage_status: Mapped[str] = mapped_column(String(30), nullable=False)
    cashless_status: Mapped[str | None] = mapped_column(String(30))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))


class RoutingRecommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "routing_recommendations"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("triage_assessments.id"), nullable=False
    )
    referral_facility_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("referral_facilities.id")
    )
    recommendation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    clinical_priority_unchanged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reasoning: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    blocked_reasons: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    confirmed_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
