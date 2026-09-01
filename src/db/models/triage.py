"""Clinical intake, observation, assessment, decision, diagnosis, and closure models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class VitalObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vital_observations"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    recorded_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heart_rate_bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    respiratory_rate_bpm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    spo2_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    systolic_bp_mmhg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    diastolic_bp_mmhg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_c: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    avpu: Mapped[str | None] = mapped_column(String(1))
    gcs_eye: Mapped[int | None] = mapped_column(SmallInteger)
    gcs_verbal: Mapped[int | None] = mapped_column(SmallInteger)
    gcs_motor: Mapped[int | None] = mapped_column(SmallInteger)
    gcs_total: Mapped[int | None] = mapped_column(SmallInteger)
    pain_score: Mapped[int | None] = mapped_column(SmallInteger)
    pain_scale: Mapped[str | None] = mapped_column(String(30))
    pain_location: Mapped[str | None] = mapped_column(String(150))
    pain_reported_by: Mapped[str | None] = mapped_column(String(30))
    oxygen_support: Mapped[str | None] = mapped_column(String(100))
    quality_notes: Mapped[str | None] = mapped_column(Text)


class Questionnaire(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questionnaires"
    __table_args__ = (UniqueConstraint("code", "version", "language_code"),)

    code: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    complaint_category: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class QuestionnaireQuestion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "questionnaire_questions"
    __table_args__ = (UniqueConstraint("questionnaire_id", "question_code"),)

    questionnaire_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questionnaires.id"), nullable=False
    )
    parent_question_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questionnaire_questions.id")
    )
    question_code: Mapped[str] = mapped_column(String(80), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_type: Mapped[str] = mapped_column(String(30), nullable=False)
    allowed_options: Mapped[dict | None] = mapped_column(JSONB)
    validation_rules: Mapped[dict | None] = mapped_column(JSONB)
    show_when: Mapped[dict | None] = mapped_column(JSONB)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    clinical_rationale: Mapped[str | None] = mapped_column(Text)


class SymptomInterview(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "symptom_interviews"
    __table_args__ = (UniqueConstraint("encounter_id", "interview_number"),)

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    questionnaire_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("questionnaires.id"), nullable=False
    )
    interview_number: Mapped[int] = mapped_column(Integer, nullable=False)
    respondent_type: Mapped[str] = mapped_column(String(30), nullable=False)
    conducted_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    language_code: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SymptomResponse(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "symptom_responses"

    interview_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("symptom_interviews.id"), nullable=False
    )
    question_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("questionnaire_questions.id"))
    question_text_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    answer_value: Mapped[dict | None] = mapped_column(JSONB)
    answer_source: Mapped[str] = mapped_column(String(30), nullable=False)
    unable_to_answer: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    answered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TriageAssessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "triage_assessments"
    __table_args__ = (UniqueConstraint("encounter_id", "assessment_number"),)

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    assessment_number: Mapped[int] = mapped_column(Integer, nullable=False)
    latest_vital_observation_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vital_observations.id")
    )
    source_interview_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("symptom_interviews.id"))
    operational_config_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("hospital_operational_configs.id"), nullable=False
    )
    assessment_status: Mapped[str] = mapped_column(String(30), nullable=False)
    proposed_esi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    maximum_allowed_esi: Mapped[int | None] = mapped_column(SmallInteger)
    recommended_esi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    possible_esi_levels: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)
    uncertainty_label: Mapped[str] = mapped_column(String(40), nullable=False)
    requires_senior_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    matched_safety_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    matched_clinical_pathways: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    missing_input_flags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    input_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    score_source: Mapped[str] = mapped_column(String(40), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmation_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))


class AssessmentSafetyAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessment_safety_actions"

    assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("triage_assessments.id"), nullable=False
    )
    action_code: Mapped[str] = mapped_column(String(100), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_staff_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completion_notes: Mapped[str | None] = mapped_column(Text)


class ClinicianDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "clinician_decisions"

    assessment_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("triage_assessments.id"), nullable=False
    )
    decision_type: Mapped[str] = mapped_column(String(24), nullable=False)
    final_esi: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    decided_by_staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    reason_text: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_decision_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("clinician_decisions.id")
    )
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EncounterDiagnosis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounter_diagnoses"

    encounter_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("encounters.id"), nullable=False)
    diagnosis_code: Mapped[str | None] = mapped_column(String(80))
    diagnosis_name: Mapped[str] = mapped_column(String(200), nullable=False)
    diagnosis_type: Mapped[str] = mapped_column(String(30), nullable=False)
    clinical_status: Mapped[str] = mapped_column(String(30), nullable=False)
    diagnosed_by_staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    diagnosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class EncounterClosure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "encounter_closures"

    encounter_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("encounters.id"), unique=True, nullable=False
    )
    disposition: Mapped[str] = mapped_column(String(40), nullable=False)
    medication_decision: Mapped[str] = mapped_column(String(40), nullable=False)
    clinical_summary: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_instructions: Mapped[str | None] = mapped_column(Text)
    closed_by_staff_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("staff.id"), nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
