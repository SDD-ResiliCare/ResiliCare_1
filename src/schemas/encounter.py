"""Encounter, queue, participant, and observation contracts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from src.schemas.common import ResourceResponse


class EncounterCreate(BaseModel):
    hospital_id: UUID
    patient_id: UUID
    encounter_code: str
    encounter_type: str = "emergency"
    arrival_mode: str | None = None
    arrived_at: datetime
    current_ward_id: UUID | None = None
    chief_complaint: str
    presenting_details: str | None = None
    symptom_onset_at: datetime | None = None
    symptom_onset_precision: str = "unknown"
    data_quality_notes: str | None = None


class EncounterResponse(ResourceResponse, EncounterCreate):
    status: str
    triaged_at: datetime | None
    care_started_at: datetime | None
    completed_at: datetime | None


class ParticipantCreate(BaseModel):
    staff_id: UUID
    role: str
    assigned_at: datetime
    assignment_reason: str | None = None


class DoctorTransferCreate(BaseModel):
    new_doctor_staff_id: UUID
    transferred_at: datetime
    reason: str


class QueueEntryCreate(BaseModel):
    encounter_id: UUID
    entered_at: datetime


class QueueCreate(BaseModel):
    hospital_id: UUID
    ward_id: UUID | None = None
    queue_code: str
    name: str
    queue_type: str


class VitalObservationCreate(BaseModel):
    recorded_by_staff_id: UUID | None = None
    source: str
    observed_at: datetime
    heart_rate_bpm: Decimal | None = Field(default=None, gt=0)
    respiratory_rate_bpm: Decimal | None = Field(default=None, gt=0)
    spo2_percent: Decimal | None = Field(default=None, ge=0, le=100)
    systolic_bp_mmhg: Decimal | None = Field(default=None, gt=0)
    diastolic_bp_mmhg: Decimal | None = Field(default=None, gt=0)
    temperature_c: Decimal | None = None
    avpu: str | None = None
    gcs_eye: int | None = Field(default=None, ge=1, le=4)
    gcs_verbal: int | None = Field(default=None, ge=1, le=5)
    gcs_motor: int | None = Field(default=None, ge=1, le=6)
    pain_score: int | None = Field(default=None, ge=0, le=10)
    pain_scale: str | None = None
    pain_location: str | None = None
    pain_reported_by: str | None = None
    oxygen_support: str | None = None
    quality_notes: str | None = None

    @model_validator(mode="after")
    def validate_gcs_components(self) -> "VitalObservationCreate":
        components = (self.gcs_eye, self.gcs_verbal, self.gcs_motor)
        if any(value is not None for value in components) and not all(value is not None for value in components):
            raise ValueError("all three GCS components are required when recording GCS")
        return self


class EncounterDiagnosisCreate(BaseModel):
    diagnosis_code: str | None = None
    diagnosis_name: str
    diagnosis_type: str
    clinical_status: str
    diagnosed_at: datetime
    notes: str | None = None


class EncounterClosureCreate(BaseModel):
    disposition: str
    medication_decision: str
    clinical_summary: str
    follow_up_instructions: str | None = None
    closed_at: datetime
