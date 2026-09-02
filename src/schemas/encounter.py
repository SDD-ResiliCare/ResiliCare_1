"""Encounter, queue, participant, and observation contracts."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from src.schemas.common import ORMModel, ResourceResponse
from src.schemas.patient import PatientResponse


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


class EncounterUpdate(BaseModel):
    arrival_mode: str | None = None
    current_ward_id: UUID | None = None
    chief_complaint: str | None = None
    presenting_details: str | None = None
    symptom_onset_at: datetime | None = None
    symptom_onset_precision: str | None = None
    data_quality_notes: str | None = None


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


class QueueUpdate(BaseModel):
    name: str | None = None
    ward_id: UUID | None = None


class QueuePriorityUpdate(BaseModel):
    priority_boost: int = Field(ge=0, le=5)
    reason: str | None = Field(default=None, max_length=1000)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def require_boost_context(self) -> "QueuePriorityUpdate":
        if self.priority_boost > 0 and (not self.reason or self.expires_at is None):
            raise ValueError("a positive priority boost requires reason and expires_at")
        return self


class QueueEntryAction(BaseModel):
    occurred_at: datetime
    reason: str | None = Field(default=None, max_length=1000)


class QueueEntryResponse(ResourceResponse):
    queue_id: UUID
    encounter_id: UUID
    status: str
    entered_at: datetime
    called_at: datetime | None
    exited_at: datetime | None
    exit_reason: str | None
    priority_boost: int
    priority_boost_reason: str | None
    priority_boost_expires_at: datetime | None
    boosted_by_staff_id: UUID | None
    reassessment_due_at: datetime | None
    last_ranked_at: datetime | None


class EncounterAllocationCreate(BaseModel):
    ward_id: UUID
    doctor_staff_id: UUID
    confirmed_at: datetime
    bed_label: str | None = Field(default=None, max_length=50)
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("confirmed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("confirmed_at must include a timezone")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason cannot be blank")
        return value.strip()


class QueueSummary(ORMModel):
    id: UUID
    hospital_id: UUID
    ward_id: UUID | None
    queue_code: str
    name: str
    queue_type: str
    status: str


class QueueWardSummary(BaseModel):
    id: UUID
    ward_code: str
    name: str
    ward_type: str


class QueueDoctorSummary(BaseModel):
    id: UUID
    employee_code: str
    first_name: str
    last_name: str | None


class DoctorWorkPatientSummary(BaseModel):
    work_item_id: UUID
    encounter_id: UUID
    encounter_code: str
    patient_id: UUID
    patient_name: str
    ward: QueueWardSummary
    status: str
    confirmed_esi: int
    queue_position: int | None
    queued_at: datetime
    started_at: datetime | None


class DoctorWorkloadResponse(BaseModel):
    doctor: QueueDoctorSummary
    availability: str
    current_patient: DoctorWorkPatientSummary | None
    waiting_count: int
    waiting_patients: list[DoctorWorkPatientSummary]


class QueueTriageSummary(BaseModel):
    assessment_id: UUID | None
    assessment_status: str | None
    predicted_esi: int | None
    possible_esi_levels: list[int]
    uncertainty_label: str | None
    requires_senior_review: bool
    safety_alert: bool
    confirmation_status: str
    decision_id: UUID | None
    final_esi: int | None
    decided_at: datetime | None


class QueueAllocationSummary(BaseModel):
    hospital_id: UUID
    hospital_name: str
    suggested_ward: QueueWardSummary | None
    suggestion_basis: str | None
    assigned_ward: QueueWardSummary | None
    primary_doctor: QueueDoctorSummary | None
    assigned_by_staff_id: UUID | None
    assigned_at: datetime | None


class RankedQueueEntryResponse(BaseModel):
    rank: int
    queue_entry_id: UUID
    queue_entry: QueueEntryResponse
    queue_status: str
    entered_at: datetime
    called_at: datetime | None
    reassessment_due_at: datetime | None
    reassessment_overdue: bool
    active_priority_boost: int
    patient: PatientResponse
    encounter: EncounterResponse
    final_esi: int | None
    safety_alert: bool
    triage: QueueTriageSummary
    allocation: QueueAllocationSummary
    vitals: dict | None = None


class CurrentQueueResponse(BaseModel):
    queue: QueueSummary
    entries: list[RankedQueueEntryResponse]


class EncounterAllocationResponse(BaseModel):
    encounter_id: UUID
    hospital_id: UUID
    ward: QueueWardSummary
    primary_doctor: QueueDoctorSummary
    location_history_id: UUID
    doctor_participant_id: UUID
    triage_assessment_id: UUID
    clinician_decision_id: UUID
    hospital_queue_entry_id: UUID
    hospital_queue_status: str
    doctor_work_item_id: UUID
    doctor_work_status: str
    doctor_queue_position: int | None
    confirmed_by_staff_id: UUID
    confirmed_at: datetime


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
