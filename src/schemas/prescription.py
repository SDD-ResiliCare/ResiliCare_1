"""Prescription contracts."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class PrescriptionItemCreate(BaseModel):
    generic_name: str
    brand_name: str | None = None
    dosage_form: str
    strength: str
    dose: str
    route: str
    frequency: str
    duration_value: int | None = Field(default=None, gt=0)
    duration_unit: str | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    is_prn: bool = False
    prn_reason: str | None = None
    instructions: str
    start_date: date | None = None
    end_date: date | None = None


class PrescriptionCreate(BaseModel):
    prescriber_participant_id: UUID
    prescription_number: str
    diagnosis_summary: str | None = None
    general_instructions: str | None = None
    items: list[PrescriptionItemCreate] = Field(min_length=1)


class PrescriptionDraftUpdate(BaseModel):
    diagnosis_summary: str | None = None
    general_instructions: str | None = None


class PrescriptionIssue(BaseModel):
    issued_at: datetime
    signed_at: datetime


class PrescriptionCancel(BaseModel):
    cancelled_at: datetime
    reason: str = Field(min_length=1)
