"""Persisted triage workflow around the existing pure clinical engine."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.confidence_scoring import score_with_confidence
from src.db.models.encounter import Encounter
from src.db.models.patient import Patient
from src.db.models.triage import (
    AssessmentSafetyAction,
    ClinicianDecision,
    Questionnaire,
    QuestionnaireQuestion,
    TriageAssessment,
    VitalObservation,
)
from src.db.repositories.triage import ClinicianDecisionRepository, TriageAssessmentRepository
from src.schemas.triage import AssessmentCreate, ClinicianDecisionCreate, QuestionnaireCreate


class TriageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.assessments = TriageAssessmentRepository(session)
        self.decisions = ClinicianDecisionRepository(session)

    async def create_questionnaire(self, payload: QuestionnaireCreate) -> Questionnaire:
        questionnaire = Questionnaire(
            code=payload.code,
            title=payload.title,
            complaint_category=payload.complaint_category,
            version=payload.version,
            language_code=payload.language_code,
            is_active=True,
        )
        self.session.add(questionnaire)
        await self.session.flush()
        question_by_code: dict[str, QuestionnaireQuestion] = {}
        for item in sorted(payload.questions, key=lambda question: question.display_order):
            parent = question_by_code.get(item.parent_question_code) if item.parent_question_code else None
            if item.parent_question_code and parent is None:
                raise HTTPException(422, f"unknown or later parent question: {item.parent_question_code}")
            values = item.model_dump(exclude={"parent_question_code"})
            question = QuestionnaireQuestion(
                questionnaire_id=questionnaire.id,
                parent_question_id=parent.id if parent else None,
                **values,
            )
            self.session.add(question)
            await self.session.flush()
            question_by_code[item.question_code] = question
        await self.session.commit()
        await self.session.refresh(questionnaire)
        return questionnaire

    async def create_assessment(
        self, encounter_id: UUID, payload: AssessmentCreate, created_by: UUID | None, hospital_id: UUID | None
    ) -> TriageAssessment:
        statement = (
            select(Patient, Encounter, VitalObservation)
            .join_from(Patient, Encounter, Encounter.patient_id == Patient.id)
            .outerjoin(VitalObservation, VitalObservation.id == payload.latest_vital_observation_id)
            .where(Encounter.id == encounter_id)
        )
        if hospital_id is not None:
            statement = statement.where(Encounter.hospital_id == hospital_id)
        row = (await self.session.execute(statement)).first()
        if row is None:
            raise HTTPException(404, "encounter not found")
        patient, encounter, vital = row
        engine_input = self._engine_input(patient, encounter, vital)
        result = score_with_confidence(engine_input, payload.proposed_esi)
        next_number = (
            await self.session.scalar(
                select(func.coalesce(func.max(TriageAssessment.assessment_number), 0) + 1).where(
                    TriageAssessment.encounter_id == encounter_id
                )
            )
        ) or 1
        snapshot = {
            "patient_id": str(patient.id),
            "vital_observation_id": str(vital.id) if vital else None,
            "symptom_interview_id": str(payload.source_interview_id) if payload.source_interview_id else None,
            "engine_input": engine_input,
        }
        encoded = json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
        assessment = await self.assessments.add(
            TriageAssessment(
                encounter_id=encounter_id,
                assessment_number=next_number,
                latest_vital_observation_id=payload.latest_vital_observation_id,
                source_interview_id=payload.source_interview_id,
                operational_config_id=payload.operational_config_id,
                assessment_status="pending_confirmation",
                proposed_esi=payload.proposed_esi,
                maximum_allowed_esi=result.get("safety_ceiling"),
                recommended_esi=result["point_estimate"],
                possible_esi_levels=result["esi_set"],
                uncertainty_label=result["confidence_label"],
                requires_senior_review=result["defer_to_senior_nurse"],
                matched_safety_rules={"rule_ids": result.get("matched_safety_rules", [])},
                matched_clinical_pathways={"pathways": result.get("ambiguous_presentations", [])},
                missing_input_flags=result.get("uncertainty_reasons", []),
                input_snapshot=snapshot,
                input_hash=hashlib.sha256(encoded).hexdigest(),
                score_source=payload.score_source,
                engine_version=payload.engine_version,
                confirmation_due_at=payload.confirmation_due_at,
                created_by_staff_id=created_by,
            )
        )
        for pathway in result.get("ambiguous_presentations", []):
            self.session.add(
                AssessmentSafetyAction(
                    assessment_id=assessment.id,
                    action_code=f"PATHWAY_{pathway['pathway_id']}",
                    instruction=pathway.get("mandatory_workup") or "Mandatory clinician safety review",
                    severity="mandatory",
                    status="pending",
                )
            )
        await self.session.commit()
        return assessment

    async def record_decision(
        self, assessment_id: UUID, payload: ClinicianDecisionCreate, staff_id: UUID, hospital_id: UUID | None
    ) -> ClinicianDecision:
        assessment = await self.assessments.get(assessment_id, for_update=True)
        if assessment is None:
            raise HTTPException(404, "triage assessment not found")
        encounter_hospital = await self.session.scalar(
            select(Encounter.hospital_id).where(Encounter.id == assessment.encounter_id)
        )
        if hospital_id is not None and encounter_hospital != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        if payload.decision_type == "accepted" and payload.final_esi != assessment.recommended_esi:
            raise HTTPException(422, "accepted decision must match recommended ESI")
        if payload.decision_type == "overridden" and not payload.reason_text:
            raise HTTPException(422, "override requires reason_text")
        decision = await self.decisions.add(
            ClinicianDecision(
                assessment_id=assessment_id,
                decided_by_staff_id=staff_id,
                **payload.model_dump(),
            )
        )
        assessment.assessment_status = "confirmed" if payload.decision_type == "accepted" else "overridden"
        await self.session.commit()
        return decision

    @staticmethod
    def _engine_input(patient: Patient, encounter: Encounter, vital: VitalObservation | None) -> dict:
        age = None
        if patient.date_of_birth:
            today = datetime.now(UTC).date()
            age = (
                today.year
                - patient.date_of_birth.year
                - ((today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day))
            )
        elif patient.estimated_age_years is not None:
            age = float(patient.estimated_age_years)
        return {
            "age_years": age,
            "chief_complaint": encounter.chief_complaint,
            "has_prior_history": False,
            "hr_bpm": float(vital.heart_rate_bpm) if vital and vital.heart_rate_bpm is not None else None,
            "rr_bpm": float(vital.respiratory_rate_bpm) if vital and vital.respiratory_rate_bpm is not None else None,
            "spo2_pct": float(vital.spo2_percent) if vital and vital.spo2_percent is not None else None,
            "sbp_mmhg": float(vital.systolic_bp_mmhg) if vital and vital.systolic_bp_mmhg is not None else None,
            "dbp_mmhg": float(vital.diastolic_bp_mmhg) if vital and vital.diastolic_bp_mmhg is not None else None,
            "temp_c": float(vital.temperature_c) if vital and vital.temperature_c is not None else None,
        }
