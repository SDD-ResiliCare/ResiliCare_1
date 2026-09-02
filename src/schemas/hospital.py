"""Hospital and ward API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from src.schemas.common import ResourceResponse


class HospitalCreate(BaseModel):
    hospital_code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=200)
    facility_type: str
    address: dict = Field(default_factory=dict)
    timezone: str = "Asia/Kolkata"
    phone: str | None = None
    email: str | None = None
    outbound_transfer_enabled: bool = False
    profile_image_path: str | None = None


class HospitalResponse(ResourceResponse, HospitalCreate):
    status: str


class HospitalUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    facility_type: str | None = None
    address: dict | None = None
    timezone: str | None = None
    phone: str | None = None
    email: str | None = None
    outbound_transfer_enabled: bool | None = None
    profile_image_path: str | None = None


class WardCreate(BaseModel):
    hospital_id: UUID
    ward_code: str
    name: str
    ward_type: str
    floor_label: str | None = None
    contact_extension: str | None = None
    capacity: int | None = Field(default=None, ge=0)


class WardResponse(ResourceResponse, WardCreate):
    status: str


class WardUpdate(BaseModel):
    name: str | None = None
    ward_type: str | None = None
    floor_label: str | None = None
    contact_extension: str | None = None
    capacity: int | None = Field(default=None, ge=0)


class EsiCareAreaRuleCreate(BaseModel):
    esi_level: int = Field(ge=1, le=5)
    ward_id: UUID
    priority: int = Field(default=1, ge=1)
    is_default: bool = False


class EscalationRouteCreate(BaseModel):
    trigger_code: str
    contact_staff_id: UUID | None = None
    contact_ward_id: UUID | None = None
    fallback_contact_name: str | None = None
    phone_extension: str | None = None
    priority: int = Field(default=1, ge=1)


class OperationalConfigCreate(BaseModel):
    version: int = Field(ge=1)
    queue_warning_threshold: int = Field(gt=0)
    surge_threshold: int = Field(gt=0)
    transfer_first_for_unsupported: bool = False
    effective_from: datetime
    effective_until: datetime | None = None
    care_area_rules: list[EsiCareAreaRuleCreate]
    escalation_routes: list[EscalationRouteCreate] = Field(default_factory=list)
