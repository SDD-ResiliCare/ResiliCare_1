"""Pydantic contracts for Kiosk audio/text intake, directives, follow-ups, and trauma merge."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KioskTextIntakeRequest(BaseModel):
    transcript: str = Field(min_length=1, description="Raw speech-to-text or typed transcript")
    patient_id: UUID | None = Field(default=None, description="Optional existing patient UUID")
    hospital_id: UUID | None = Field(default=None, description="Optional hospital UUID")
    language_code: str = Field(default="en", description="Detected or selected language code")


class KioskFollowUpQuestion(BaseModel):
    question_code: str
    question_text: str
    clinical_intent: str
    risk_level: str = "ROUTINE"  # "CRITICAL", "MODERATE", "ROUTINE"
    escalate_on_yes: bool = False
    escalated_esi_ceiling: int | None = Field(default=None, ge=1, le=5)


class KioskIntakeResponse(BaseModel):
    transcript: str
    speech_detected: bool = True
    acoustic_distress_flag: bool = False
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_gate_passed: bool
    fallback_to_touch: bool = False
    layout_directive: str  # "AUDIO_CONFIRMED" | "SWITCH_TO_TOUCH_GRID" | "CRITICAL_RED_FLAG_LOCK" | "PROMPT_FOLLOW_UPS"
    extracted_complaint: str | None = None
    patient_alias: str
    clinical_acuity_red_flags: list[str] = Field(default_factory=list)
    suggested_follow_up_questions: list[KioskFollowUpQuestion] = Field(default_factory=list)
    differential_matches: list[dict] = Field(default_factory=list)


class FollowUpAnswer(BaseModel):
    question_code: str
    answer_yes: bool


class KioskFollowUpSubmitRequest(BaseModel):
    extracted_complaint: str
    answers: list[FollowUpAnswer]


class KioskFollowUpSubmitResponse(BaseModel):
    acuity_escalated: bool
    effective_esi_ceiling: int
    matched_safety_pathway: str | None = None
    safety_actions: list[str] = Field(default_factory=list)
    summary_for_nurse: str


class TraumaIntakeRequest(BaseModel):
    hospital_id: UUID
    estimated_age: int | None = 35
    gender_presentation: str = "unknown"  # "male", "female", "unknown"
    observed_trauma_cues: list[str] = Field(default_factory=list)


class TraumaIntakeResponse(BaseModel):
    patient_id: UUID
    encounter_id: UUID
    alias: str
    is_unidentified: bool
    status: str
    created_at: datetime


class ReconcileIdentityRequest(BaseModel):
    trauma_patient_id: UUID
    target_master_patient_id: UUID
    reason: str


class ReconcileIdentityResponse(BaseModel):
    success: bool
    trauma_patient_id: UUID
    target_master_patient_id: UUID
    reparented_encounters_count: int
    reparented_vitals_count: int
    reparented_interviews_count: int
    reparented_assessments_count: int
    reparented_decisions_count: int
    merged_at: datetime
