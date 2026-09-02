"""Application profile and role mappings for Supabase Auth identities."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserProfile(TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (CheckConstraint("status in ('invited', 'active', 'suspended', 'disabled')", name="status"),)

    auth_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str | None] = mapped_column(String(200))
    preferred_language: Mapped[str | None] = mapped_column(String(20))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (
        CheckConstraint(
            "role_name in ('platform_admin', 'administrator', 'doctor', 'nurse', "
            "'receptionist', 'billing_staff', 'patient')",
            name="role_name",
        ),
        CheckConstraint(
            "(role_name in ('platform_admin', 'patient') and hospital_id is null) or "
            "(role_name in ('administrator', 'doctor', 'nurse', 'receptionist', 'billing_staff') "
            "and hospital_id is not null)",
            name="scope",
        ),
        CheckConstraint("revoked_at is null or revoked_at >= granted_at", name="revocation"),
        Index(
            "uq_user_roles_active_global_role",
            "auth_user_id",
            "role_name",
            unique=True,
            postgresql_where=text("hospital_id is null and revoked_at is null"),
        ),
        Index(
            "uq_user_roles_active_hospital_role",
            "auth_user_id",
            "role_name",
            "hospital_id",
            unique=True,
            postgresql_where=text("hospital_id is not null and revoked_at is null"),
        ),
        Index(
            "uq_user_roles_active_primary",
            "auth_user_id",
            unique=True,
            postgresql_where=text("is_primary and revoked_at is null"),
        ),
        Index(
            "ix_user_roles_hospital_active",
            "hospital_id",
            "role_name",
            postgresql_where=text("revoked_at is null"),
        ),
    )

    auth_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.auth_user_id", ondelete="CASCADE"), nullable=False
    )
    role_name: Mapped[str] = mapped_column(String(32), nullable=False)
    hospital_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospitals.id", ondelete="CASCADE")
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    granted_by_auth_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="SET NULL")
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

