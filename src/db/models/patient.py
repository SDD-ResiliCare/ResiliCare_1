"""Patient identity, portal access, allergies, and conditions."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Patient(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patients"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    estimated_age_years: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    sex_at_birth: Mapped[str | None] = mapped_column(String(30))
    gender_identity: Mapped[str | None] = mapped_column(String(50))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[dict | None] = mapped_column(JSONB)
    preferred_language: Mapped[str | None] = mapped_column(String(20))
    profile_image_path: Mapped[str | None] = mapped_column(Text)
    deceased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class PatientIdentifier(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient_identifiers"
    __table_args__ = (UniqueConstraint("hospital_id", "identifier_type", "identifier_value"),)

    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(40), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(120), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)


class PatientAccessLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient_access_links"
    __table_args__ = (UniqueConstraint("patient_id", "auth_user_id"),)

    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    auth_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), nullable=False
    )
    relationship: Mapped[str] = mapped_column(String(30), nullable=False)
    access_level: Mapped[str] = mapped_column(String(30), nullable=False)
    identity_verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class PatientAllergy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient_allergies"

    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    substance: Mapped[str] = mapped_column(String(200), nullable=False)
    reaction: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(String(24))
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False)
    recorded_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PatientCondition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "patient_conditions"

    patient_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    condition_code: Mapped[str | None] = mapped_column(String(80))
    condition_name: Mapped[str] = mapped_column(String(200), nullable=False)
    clinical_status: Mapped[str] = mapped_column(String(24), nullable=False)
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False)
    onset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_by_staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
