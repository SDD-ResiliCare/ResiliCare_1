"""Patient API schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.common import ResourceResponse


class PatientCreate(BaseModel):
    first_name: str
    last_name: str | None = None
    date_of_birth: date | None = None
    estimated_age_years: Decimal | None = Field(default=None, ge=0, le=130)
    sex_at_birth: str | None = None
    gender_identity: str | None = None
    phone: str | None = None
    email: str | None = None
    address: dict | None = None
    preferred_language: str | None = None
    profile_image_path: str | None = None

    @model_validator(mode="after")
    def require_age_information(self) -> "PatientCreate":
        if self.date_of_birth is None and self.estimated_age_years is None:
            raise ValueError("date_of_birth or estimated_age_years is required")
        return self


class PatientResponse(ResourceResponse, PatientCreate):
    status: str


class PatientIdentifierCreate(BaseModel):
    hospital_id: UUID
    identifier_type: str = "mrn"
    identifier_value: str
    valid_from: date


class PatientAllergyCreate(BaseModel):
    substance: str
    reaction: str | None = None
    severity: str | None = None
    verification_status: str
    recorded_at: datetime


class PatientConditionCreate(BaseModel):
    condition_code: str | None = None
    condition_name: str
    clinical_status: str
    verification_status: str
    onset_at: datetime | None = None
    resolved_at: datetime | None = None
    notes: str | None = None


class PatientAccessLinkCreate(BaseModel):
    auth_user_id: UUID
    relationship: str
    access_level: str
    identity_verified_at: datetime
    granted_at: datetime
