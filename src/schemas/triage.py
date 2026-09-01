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
