"""Symptom interview, assessment, safety, and clinician decision contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SymptomInterviewCreate(BaseModel):
    questionnaire_id: UUID
    respondent_type: str
    conducted_by_staff_id: UUID | None = None
    language_code: str = "en"
    started_at: datetime


class SymptomResponseCreate(BaseModel):
    question_id: UUID | None = None
    question_text_snapshot: str
    answer_value: dict | None = None
    answer_source: str
    unable_to_answer: bool = False
    notes: str | None = None
    answered_at: datetime


class AssessmentCreate(BaseModel):
    operational_config_id: UUID
    latest_vital_observation_id: UUID | None = None
    source_interview_id: UUID | None = None
    proposed_esi: int = Field(ge=1, le=5)
    score_source: str
    engine_version: str
    confirmation_due_at: datetime | None = None


class ClinicianDecisionCreate(BaseModel):
    decision_type: str
    final_esi: int = Field(ge=1, le=5)
    reason_code: str
    reason_text: str | None = None
    decided_at: datetime


class SafetyActionUpdate(BaseModel):
    status: str
    notes: str | None = None


class QuestionnaireQuestionCreate(BaseModel):
    parent_question_code: str | None = None
    question_code: str
    question_text: str
    answer_type: str
    allowed_options: dict | None = None
    validation_rules: dict | None = None
    show_when: dict | None = None
    display_order: int = Field(ge=0)
    clinical_rationale: str | None = None


class QuestionnaireCreate(BaseModel):
    code: str
    title: str
    complaint_category: str
    version: int = Field(ge=1)
    language_code: str = "en"
    questions: list[QuestionnaireQuestionCreate] = Field(min_length=1)


class QuestionnaireUpdate(BaseModel):
    title: str | None = None
    complaint_category: str | None = None
    is_active: bool | None = None


class TreeSHAPAttribution(BaseModel):
    feature_name: str
    raw_value: float
    shap_impact: float
    direction: str


class TopContributingFactor(BaseModel):
    feature: str
    value: str
    urgency_impact: str
    weight: float


class MLTriagePredictionRequest(BaseModel):
    encounter_id: str | None = None
    age: float | None = None
    sex: str | None = None
    arrival_mode: str | None = None
    chief_complaint: str | None = None
    presenting_details: str | None = None
    heart_rate_bpm: float | None = None
    respiratory_rate_bpm: float | None = None
    spo2_percent: float | None = None
    systolic_bp_mmhg: float | None = None
    diastolic_bp_mmhg: float | None = None
    temperature_c: float | None = None
    avpu: str | None = None
    gcs_total: int | None = None
    pain_score: int | None = None
    safety_ceiling: int | None = Field(default=None, ge=1, le=5)


class MLTriagePredictionResponse(BaseModel):
    encounter_id: str | None = None
    proposed_esi: int = Field(ge=1, le=5)
    final_esi: int = Field(ge=1, le=5)
    safety_ceiling: int | None = None
    safety_override_applied: bool = False
    confidence_score: float = Field(ge=0.0, le=1.0)
    prediction_set: list[int]
    class_probabilities: dict[str, float]
    is_uncertain: bool
    uncertainty_reasons: list[str]
    top_contributing_factors: list[TopContributingFactor]
    treeshap_attributions: list[TreeSHAPAttribution]
    clinical_rationale: str

