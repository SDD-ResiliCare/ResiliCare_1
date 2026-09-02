"""Persisted triage workflow around the existing pure clinical engine."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.confidence_scoring import score_with_confidence
from src.core.safety_rules import evaluate_safety_rules
from src.db.models.encounter import Encounter
from src.db.models.organization import EsiCareAreaRule, HospitalOperationalConfig, Ward
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
from src.ml import ESITriagePipeline
from src.schemas.triage import (
    AssessmentCreate,
    ClinicianDecisionCreate,
    MLTriagePredictionRequest,
    MLTriagePredictionResponse,
    QuestionnaireCreate,
    TopContributingFactor,
    TreeSHAPAttribution,
)
from src.services.clinical_overview_service import build_triage_overview


class TriageService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.assessments = TriageAssessmentRepository(session)
        self.decisions = ClinicianDecisionRepository(session)
        self._ml_pipeline: ESITriagePipeline | None = None

    def _get_ml_pipeline(self) -> ESITriagePipeline:
        if self._ml_pipeline is None:
            self._ml_pipeline = ESITriagePipeline()
        return self._ml_pipeline

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
        if payload.latest_vital_observation_id is not None and (
            vital is None or vital.encounter_id != encounter_id
        ):
            raise HTTPException(422, "latest vital observation must belong to this encounter")
        operational_config = await self.session.scalar(
            select(HospitalOperationalConfig).where(
                HospitalOperationalConfig.id == payload.operational_config_id,
                HospitalOperationalConfig.hospital_id == encounter.hospital_id,
            )
        )
        if operational_config is None:
            raise HTTPException(422, "operational config must belong to the encounter hospital")
        engine_input = self._engine_input(patient, encounter, vital)
        result = score_with_confidence(engine_input, payload.proposed_esi)
        recommendation = (
            await self.session.execute(
                select(EsiCareAreaRule, Ward)
                .join(Ward, Ward.id == EsiCareAreaRule.ward_id)
                .where(
                    EsiCareAreaRule.operational_config_id == payload.operational_config_id,
                    EsiCareAreaRule.esi_level == result["point_estimate"],
                    Ward.hospital_id == encounter.hospital_id,
                    Ward.status == "active",
                )
                .order_by(EsiCareAreaRule.is_default.desc(), EsiCareAreaRule.priority)
                .limit(1)
            )
        ).first()
        recommended_rule, recommended_ward = recommendation if recommendation else (None, None)
        ai_overview, ai_overview_factors = build_triage_overview(
            result,
            ward_id=recommended_rule.ward_id if recommended_rule else None,
            ward_name=recommended_ward.name if recommended_ward else None,
        )

        snapshot = {
            "patient_id": str(patient.id),
            "vital_observation_id": str(vital.id) if vital else None,
            "symptom_interview_id": str(payload.source_interview_id) if payload.source_interview_id else None,
            "engine_input": engine_input,
        }

        # If score_source is ML or hybrid, compute and persist full ML & TreeSHAP predictions in dedicated ml_output column
        ml_output = None
        if payload.score_source and any(
            k in payload.score_source.lower() for k in ("ml", "lgbm", "hybrid", "model", "tree")
        ):
            try:
                pipeline = self._get_ml_pipeline()
                ml_input = {
                    "encounter_id": str(encounter.encounter_code or encounter.id),
                    "age": engine_input.get("age_years"),
                    "sex": patient.sex_at_birth,
                    "arrival_mode": encounter.arrival_mode,
                    "chief_complaint": encounter.chief_complaint,
                    "presenting_details": encounter.presenting_details,
                    "heart_rate_bpm": engine_input.get("hr_bpm"),
                    "respiratory_rate_bpm": engine_input.get("rr_bpm"),
                    "spo2_percent": engine_input.get("spo2_pct"),
                    "systolic_bp_mmhg": engine_input.get("sbp_mmhg"),
                    "diastolic_bp_mmhg": engine_input.get("dbp_mmhg"),
                    "temperature_c": engine_input.get("temp_c"),
                    "avpu": vital.avpu if vital else "A",
                    "gcs_total": vital.gcs_total if vital else 15,
                    "pain_score": vital.pain_score if vital else 0,
                }
                ml_output = pipeline.predict_encounter(ml_input, safety_ceiling=result.get("safety_ceiling"))
            except Exception as ml_err:  # noqa: BLE001
                ml_output = {"error": str(ml_err)}

        next_number = (
            await self.session.scalar(
                select(func.coalesce(func.max(TriageAssessment.assessment_number), 0) + 1).where(
                    TriageAssessment.encounter_id == encounter_id
                )
            )
        ) or 1

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
                recommended_ward_id=recommended_rule.ward_id if recommended_rule else None,
                possible_esi_levels=result["esi_set"],
                uncertainty_label=result["confidence_label"],
                requires_senior_review=result["defer_to_senior_nurse"],
                matched_safety_rules={"rule_ids": result.get("matched_safety_rules", [])},
                matched_clinical_pathways={"pathways": result.get("ambiguous_presentations", [])},
                missing_input_flags=result.get("uncertainty_reasons", []),
                ai_overview=ai_overview,
                ai_overview_factors=ai_overview_factors,
                input_snapshot=snapshot,
                ml_output=ml_output,
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

    async def predict_ml(self, encounter_id: UUID, hospital_id: UUID | None) -> MLTriagePredictionResponse:
        """Fetch live encounter & vitals from Supabase, evaluate safety ceilings, and run ESI ML inference."""
        latest_vital_subquery = (
            select(VitalObservation.id)
            .where(VitalObservation.encounter_id == encounter_id)
            .order_by(VitalObservation.observed_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        statement = (
            select(Patient, Encounter, VitalObservation)
            .join_from(Patient, Encounter, Encounter.patient_id == Patient.id)
            .outerjoin(VitalObservation, VitalObservation.id == latest_vital_subquery)
            .where(Encounter.id == encounter_id)
        )
        if hospital_id is not None:
            statement = statement.where(Encounter.hospital_id == hospital_id)
        row = (await self.session.execute(statement)).first()
        if row is None:
            raise HTTPException(404, "encounter not found")
        patient, encounter, vital = row

        engine_input = self._engine_input(patient, encounter, vital)
        safety = evaluate_safety_rules(engine_input)
        safety_ceiling = safety.get("ceiling")

        pipeline_input = {
            "encounter_id": str(encounter.encounter_code or encounter.id),
            "age": engine_input.get("age_years"),
            "sex": patient.sex_at_birth,
            "arrival_mode": encounter.arrival_mode,
            "chief_complaint": encounter.chief_complaint,
            "presenting_details": encounter.presenting_details,
            "heart_rate_bpm": engine_input.get("hr_bpm"),
            "respiratory_rate_bpm": engine_input.get("rr_bpm"),
            "spo2_percent": engine_input.get("spo2_pct"),
            "systolic_bp_mmhg": engine_input.get("sbp_mmhg"),
            "diastolic_bp_mmhg": engine_input.get("dbp_mmhg"),
            "temperature_c": engine_input.get("temp_c"),
            "avpu": vital.avpu if vital else "A",
            "gcs_total": vital.gcs_total if vital else 15,
            "pain_score": vital.pain_score if vital else 0,
        }

        pipeline = self._get_ml_pipeline()
        raw_pred = pipeline.predict_encounter(pipeline_input, safety_ceiling=safety_ceiling)

        return MLTriagePredictionResponse(
            encounter_id=str(encounter.id),
            proposed_esi=raw_pred["proposed_esi"],
            final_esi=raw_pred["final_esi"],
            safety_ceiling=safety_ceiling,
            safety_override_applied=raw_pred["safety_override_applied"],
            confidence_score=raw_pred["confidence_score"],
            prediction_set=raw_pred["prediction_set"],
            class_probabilities=raw_pred["class_probabilities"],
            is_uncertain=raw_pred["is_uncertain"],
            uncertainty_reasons=raw_pred["uncertainty_reasons"],
            top_contributing_factors=[TopContributingFactor(**f) for f in raw_pred["top_contributing_factors"]],
            treeshap_attributions=[TreeSHAPAttribution(**a) for a in raw_pred.get("treeshap_attributions", [])],
            clinical_rationale=raw_pred["clinical_rationale"],
        )

    def predict_simulation(self, payload: MLTriagePredictionRequest) -> MLTriagePredictionResponse:
        """Run ML prediction and TreeSHAP explainability for simulated or uncommitted patient inputs."""
        pipeline = self._get_ml_pipeline()
        sim_input = {
            "encounter_id": payload.encounter_id or "SIMULATION-001",
            "age": payload.age,
            "sex": payload.sex,
            "arrival_mode": payload.arrival_mode,
            "chief_complaint": payload.chief_complaint,
            "presenting_details": payload.presenting_details,
            "heart_rate_bpm": payload.heart_rate_bpm,
            "respiratory_rate_bpm": payload.respiratory_rate_bpm,
            "spo2_percent": payload.spo2_percent,
            "systolic_bp_mmhg": payload.systolic_bp_mmhg,
            "diastolic_bp_mmhg": payload.diastolic_bp_mmhg,
            "temperature_c": payload.temperature_c,
            "avpu": payload.avpu or "A",
            "gcs_total": payload.gcs_total or 15,
            "pain_score": payload.pain_score or 0,
        }

        safety_input = {
            "age_years": payload.age,
            "chief_complaint": payload.chief_complaint,
            "hr_bpm": payload.heart_rate_bpm,
            "rr_bpm": payload.respiratory_rate_bpm,
            "spo2_pct": payload.spo2_percent,
            "sbp_mmhg": payload.systolic_bp_mmhg,
            "dbp_mmhg": payload.diastolic_bp_mmhg,
            "temp_c": payload.temperature_c,
        }
        safety = evaluate_safety_rules(safety_input)
        computed_ceiling = safety.get("ceiling")

        if payload.safety_ceiling is not None:
            effective_ceiling = (
                min(payload.safety_ceiling, computed_ceiling) if computed_ceiling else payload.safety_ceiling
            )
        else:
            effective_ceiling = computed_ceiling

        raw_pred = pipeline.predict_encounter(sim_input, safety_ceiling=effective_ceiling)

        return MLTriagePredictionResponse(
            encounter_id=payload.encounter_id,
            proposed_esi=raw_pred["proposed_esi"],
            final_esi=raw_pred["final_esi"],
            safety_ceiling=effective_ceiling,
            safety_override_applied=raw_pred["safety_override_applied"],
            confidence_score=raw_pred["confidence_score"],
            prediction_set=raw_pred["prediction_set"],
            class_probabilities=raw_pred["class_probabilities"],
            is_uncertain=raw_pred["is_uncertain"],
            uncertainty_reasons=raw_pred["uncertainty_reasons"],
            top_contributing_factors=[TopContributingFactor(**f) for f in raw_pred["top_contributing_factors"]],
            treeshap_attributions=[TreeSHAPAttribution(**a) for a in raw_pred.get("treeshap_attributions", [])],
            clinical_rationale=raw_pred["clinical_rationale"],
        )

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
