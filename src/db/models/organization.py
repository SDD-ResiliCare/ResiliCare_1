"""Hospital, ward, configuration, and referral-facility models."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Hospital(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hospitals"

    hospital_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    outbound_transfer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    profile_image_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class Ward(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "wards"
    __table_args__ = (UniqueConstraint("hospital_id", "ward_code"),)

    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    ward_code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    ward_type: Mapped[str] = mapped_column(String(50), nullable=False)
    floor_label: Mapped[str | None] = mapped_column(String(50))
    contact_extension: Mapped[str | None] = mapped_column(String(20))
    capacity: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class HospitalOperationalConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "hospital_operational_configs"
    __table_args__ = (UniqueConstraint("hospital_id", "version"),)

    hospital_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("hospitals.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    queue_warning_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    surge_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    transfer_first_for_unsupported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class EsiCareAreaRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "esi_care_area_rules"
    __table_args__ = (UniqueConstraint("operational_config_id", "esi_level", "ward_id"),)

    operational_config_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospital_operational_configs.id"), nullable=False
    )
    esi_level: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    ward_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class EscalationRoute(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "escalation_routes"

    operational_config_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospital_operational_configs.id"), nullable=False
    )
    trigger_code: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    contact_ward_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("wards.id"))
    fallback_contact_name: Mapped[str | None] = mapped_column(String(150))
    phone_extension: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ReferralFacility(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "referral_facilities"

    facility_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    phone: Mapped[str | None] = mapped_column(String(32))
    supported_specialties: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FacilitySchemeTerm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "facility_scheme_terms"
    __table_args__ = (UniqueConstraint("facility_id", "scheme_code", "valid_from"),)

    facility_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("referral_facilities.id"), nullable=False
    )
    scheme_code: Mapped[str] = mapped_column(String(80), nullable=False)
    cashless_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    room_rent_cap: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
