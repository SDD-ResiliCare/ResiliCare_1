"""Staff identity, professional profile, and ward-assignment models."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Staff(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff"
    __table_args__ = (UniqueConstraint("hospital_id", "employee_code"),)

    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    auth_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="SET NULL"), unique=True
    )
    employee_code: Mapped[str] = mapped_column(String(50), nullable=False)
    staff_type: Mapped[str] = mapped_column(String(32), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    profile_image_path: Mapped[str | None] = mapped_column(Text)
    employment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    joined_on: Mapped[date] = mapped_column(Date, nullable=False)
    left_on: Mapped[date | None] = mapped_column(Date)


class ClinicalStaffProfile(TimestampMixin, Base):
    __tablename__ = "clinical_staff_profiles"

    staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), primary_key=True)
    registration_number: Mapped[str | None] = mapped_column(String(100))
    registration_authority: Mapped[str | None] = mapped_column(String(150))
    qualification: Mapped[str | None] = mapped_column(String(200))
    specialty: Mapped[str | None] = mapped_column(String(120))
    practice_started_on: Mapped[date | None] = mapped_column(Date)
    professional_grade: Mapped[str | None] = mapped_column(String(100))
    bio: Mapped[str | None] = mapped_column(Text)


class StaffWardAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "staff_ward_assignments"

    staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    ward_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"), nullable=False)
    role_in_ward: Mapped[str] = mapped_column(String(80), nullable=False)
    is_primary_ward: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    assigned_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
