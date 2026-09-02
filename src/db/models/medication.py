"""Prescription and medication-item models."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Prescription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prescriptions"
    __table_args__ = (UniqueConstraint("encounter_id", "prescription_number", "revision_number"),)

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    prescriber_participant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("encounter_participants.id"), nullable=False
    )
    prescription_number: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    diagnosis_summary: Mapped[str | None] = mapped_column(Text)
    general_instructions: Mapped[str | None] = mapped_column(Text)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    supersedes_prescription_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("prescriptions.id")
    )


class PrescriptionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "prescription_items"

    prescription_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("prescriptions.id"), nullable=False)
    generic_name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(200))
    dosage_form: Mapped[str] = mapped_column(String(80), nullable=False)
    strength: Mapped[str] = mapped_column(String(80), nullable=False)
    dose: Mapped[str] = mapped_column(String(80), nullable=False)
    route: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency: Mapped[str] = mapped_column(String(100), nullable=False)
    duration_value: Mapped[int | None] = mapped_column(Integer)
    duration_unit: Mapped[str | None] = mapped_column(String(30))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    is_prn: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    prn_reason: Mapped[str | None] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
