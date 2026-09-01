"""Staff and assignment API schemas."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from src.schemas.common import ResourceResponse


class StaffCreate(BaseModel):
    hospital_id: UUID
    employee_code: str
    staff_type: str
    first_name: str
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    profile_image_path: str | None = None
    joined_on: date
    registration_number: str | None = None
    registration_authority: str | None = None
    qualification: str | None = None
    specialty: str | None = None
    practice_started_on: date | None = None
    professional_grade: str | None = None
    bio: str | None = None


class StaffResponse(ResourceResponse):
    hospital_id: UUID
    employee_code: str
    staff_type: str
    first_name: str
    last_name: str | None
    phone: str | None
    email: str | None
    profile_image_path: str | None
    employment_status: str
    joined_on: date


class WardAssignmentCreate(BaseModel):
    ward_id: UUID
    role_in_ward: str
    is_primary_ward: bool = False
    assigned_from: datetime
