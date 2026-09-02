"""Service layer for NLP Kiosk intake, dynamic follow-up questioning, and trauma identity reconciliation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.clinical_differentials import match_ambiguous_presentations
from src.db.models.encounter import Encounter
from src.db.models.patient import Patient
from src.db.models.triage import ClinicianDecision, SymptomInterview, TriageAssessment, VitalObservation
from src.nlp.text_pipeline import process_kiosk_text, resolve_kiosk_chief_complaint
from src.schemas.kiosk import (
    KioskFollowUpQuestion,
    KioskFollowUpSubmitRequest,
    KioskFollowUpSubmitResponse,
    KioskIntakeResponse,
    KioskTextIntakeRequest,
    ReconcileIdentityRequest,
    ReconcileIdentityResponse,
    TraumaIntakeRequest,
    TraumaIntakeResponse,
)

# Sourced clinical rule-out questions for high-frequency emergency complaints
QUESTION_BANK: dict[str, list[dict[str, Any]]] = {
    "chest pain": [
        {
            "question_code": "chest_radiation",
            "question_text": "Does the pain radiate to your jaw, neck, back, or left arm?",
            "clinical_intent": "Acute Coronary Syndrome (ACS) Radiation Marker",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
        {
            "question_code": "chest_dyspnea_sweat",
            "question_text": "Are you experiencing shortness of breath, cold sweats, or nausea?",
            "clinical_intent": "Autonomic / Ischemia Associated Symptoms",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
    ],
    "lower abdominal pain": [
        {
            "question_code": "abdo_gi_bleed",
            "question_text": "Are you vomiting blood, passing black stools, or feeling severely faint?",
            "clinical_intent": "Gastrointestinal Hemorrhage / Hemodynamic Collapse Rule-out",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
        {
            "question_code": "abdo_fever_guarding",
            "question_text": "Is there a high fever or sudden, severe rigid tenderness in your belly?",
            "clinical_intent": "Peritonitis / Acute Abdomen / Sepsis Rule-out",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
    ],
    "syncope": [
        {
            "question_code": "syncope_complete_loc",
            "question_text": "Did you lose consciousness completely, even for a few seconds?",
            "clinical_intent": "True Loss of Consciousness vs Lightheadedness",
            "risk_level": "MODERATE",
            "escalate_on_yes": False,
            "escalated_esi_ceiling": 3,
        },
        {
            "question_code": "syncope_palpitations_trauma",
            "question_text": "Did you feel rapid heart racing before fainting, or suffer a head/chest injury?",
            "clinical_intent": "Cardiogenic Syncope / Secondary Trauma Rule-out",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
    ],
    "pelvic pain": [
        {
            "question_code": "pelvic_pregnancy_risk",
            "question_text": "Is there any possibility of pregnancy or a delayed menstrual cycle?",
            "clinical_intent": "Ectopic Pregnancy Safety Rule-out (ACOG)",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
        {
            "question_code": "pelvic_severe_unilateral",
            "question_text": "Is the pain sudden, sharp, and predominantly on one side?",
            "clinical_intent": "Ovarian Torsion / Ruptured Cyst Rule-out",
            "risk_level": "CRITICAL",
            "escalate_on_yes": True,
            "escalated_esi_ceiling": 2,
        },
    ],
}

DEFAULT_QUESTIONS: list[dict[str, Any]] = [
    {
        "question_code": "general_breathing_diff",
        "question_text": "Are you having trouble breathing or catching your breath?",
        "clinical_intent": "Respiratory Distress Rule-out",
        "risk_level": "CRITICAL",
        "escalate_on_yes": True,
        "escalated_esi_ceiling": 2,
    },
    {
        "question_code": "general_sudden_onset",
        "question_text": "Did these symptoms start very suddenly within the last hour?",
        "clinical_intent": "Acute vs Chronic Presentation Differentiation",
        "risk_level": "MODERATE",
        "escalate_on_yes": False,
        "escalated_esi_ceiling": 3,
    },
]


class KioskService:
    def __init__(self, session: AsyncSession):
        self.session = session

    def get_follow_up_questions(self, complaint: str | None) -> list[KioskFollowUpQuestion]:
        """Resolve targeted 2-question rule-out tree based on extracted chief complaint."""
        if not complaint:
            raw_questions = DEFAULT_QUESTIONS
        else:
            complaint_key = complaint.strip().lower()
            raw_questions = QUESTION_BANK.get(complaint_key, DEFAULT_QUESTIONS)
        return [KioskFollowUpQuestion(**q) for q in raw_questions]

    def evaluate_follow_up_answers(self, payload: KioskFollowUpSubmitRequest) -> KioskFollowUpSubmitResponse:
        """Evaluate client's follow-up responses and compute the resulting safety ceiling."""
        complaint = payload.extracted_complaint.strip().lower()
        available_questions = self.get_follow_up_questions(complaint)
        question_map = {q.question_code: q for q in available_questions}

        escalated = False
        highest_ceiling = 3  # Default ambiguous presentation baseline
        positive_intents: list[str] = []

        for answer in payload.answers:
            if answer.answer_yes and answer.question_code in question_map:
                question = question_map[answer.question_code]
                positive_intents.append(question.clinical_intent)
                if question.escalate_on_yes:
                    escalated = True
                    target_ceiling = question.escalated_esi_ceiling or 2
                    highest_ceiling = min(highest_ceiling, target_ceiling)

        safety_actions = []
        pathway = None
        if "chest" in complaint:
            pathway = "ACUTE_CHEST_DISCOMFORT"
            safety_actions = ["12-lead ECG within 10 minutes", "Serial troponin draw", "Continuous cardiac telemetry"]
        elif "abdominal" in complaint or "stomach" in complaint:
            pathway = "ACUTE_LOWER_ABDOMINAL_OR_PELVIC_PAIN"
            safety_actions = ["Urgent abdominal ultrasound", "CBC and type & screen", "Surgical consultation review"]
        elif "syncope" in complaint:
            pathway = "SYNCOPE_OR_NEAR_SYNCOPE"
            safety_actions = ["Orthostatic vital signs", "12-lead ECG", "Fingerstick blood glucose check"]
        elif "pelvic" in complaint:
            pathway = "ACUTE_LOWER_ABDOMINAL_OR_PELVIC_PAIN"
            safety_actions = ["Immediate urine/serum hCG", "Pelvic ultrasonography", "Urgent OB/GYN evaluation"]

        summary_note = (
            f"Kiosk follow-up screening for '{complaint}': Acuity escalated to ESI {highest_ceiling} "
            f"due to confirmed risks: {', '.join(positive_intents)}."
            if escalated
            else f"Kiosk follow-up screening for '{complaint}': Standard rule-out protocol active (ESI {highest_ceiling})."
        )

        return KioskFollowUpSubmitResponse(
            acuity_escalated=escalated,
            effective_esi_ceiling=highest_ceiling,
            matched_safety_pathway=pathway,
            safety_actions=safety_actions,
            summary_for_nurse=summary_note,
        )

    def process_text_intake(self, payload: KioskTextIntakeRequest) -> KioskIntakeResponse:
        """Run standard text pipeline, differential matching, and dynamic question generation."""
        kiosk_result = process_kiosk_text(payload.transcript)
        extracted = resolve_kiosk_chief_complaint(kiosk_result)

        differential_matches = []
        if extracted:
            differential_matches = match_ambiguous_presentations({"chief_complaint": extracted})

        follow_ups = self.get_follow_up_questions(extracted)

        # Determine layout directive: Critical Red Flags take highest safety precedence
        if kiosk_result.get("clinical_acuity_red_flags"):
            layout_directive = "CRITICAL_RED_FLAG_LOCK"
            fallback_to_touch = False
        elif not kiosk_result.get("confidence_gate_passed") or not extracted:
            layout_directive = "SWITCH_TO_TOUCH_GRID"
            fallback_to_touch = True
        elif follow_ups:
            layout_directive = "PROMPT_FOLLOW_UPS"
            fallback_to_touch = False
        else:
            layout_directive = "AUDIO_CONFIRMED"
            fallback_to_touch = False


        return KioskIntakeResponse(
            transcript=kiosk_result.get("transcript", payload.transcript),
            speech_detected=True,
            acoustic_distress_flag=False,
            confidence_score=1.0 if kiosk_result.get("confidence_gate_passed") else 0.2,
            confidence_gate_passed=kiosk_result.get("confidence_gate_passed", False),
            fallback_to_touch=fallback_to_touch,
            layout_directive=layout_directive,
            extracted_complaint=extracted,
            patient_alias=kiosk_result.get("patient_alias") or f"Trauma-Unknown-{str(uuid.uuid4())[:4]}",
            clinical_acuity_red_flags=kiosk_result.get("clinical_acuity_red_flags", []),
            suggested_follow_up_questions=follow_ups,
            differential_matches=differential_matches,
        )

    async def create_trauma_intake(self, payload: TraumaIntakeRequest) -> TraumaIntakeResponse:
        """Create a shadow patient record and active emergency encounter for an unidentified arrival."""
        gender_code = (payload.gender_presentation or "unknown").lower()
        gender_label = "Male" if "male" in gender_code else "Female" if "female" in gender_code else "Unknown"
        age = payload.estimated_age or 35
        unique_suffix = str(uuid.uuid4())[:4].upper()
        alias = f"Trauma-{gender_label}-{age}-{unique_suffix}"

        now = datetime.now(UTC)
        patient_id = uuid.uuid4()
        patient = Patient(
            id=patient_id,
            first_name=alias,
            last_name="(Unidentified)",
            estimated_age_years=Decimal(str(age)),
            sex_at_birth=gender_code if gender_code in ("male", "female") else None,
            status="active",
        )
        self.session.add(patient)
        await self.session.flush()

        encounter_id = uuid.uuid4()
        encounter_code = f"TRM-{unique_suffix}"
        cues = ", ".join(payload.observed_trauma_cues) if payload.observed_trauma_cues else "None recorded"
        encounter = Encounter(
            id=encounter_id,
            hospital_id=payload.hospital_id,
            patient_id=patient.id,
            encounter_code=encounter_code,
            encounter_type="emergency",
            status="arrived",
            arrived_at=now,
            chief_complaint="Unidentified Acute Trauma / Silent Arrival",
            presenting_details=f"Shadow trauma intake. Observed cues: {cues}",
        )
        self.session.add(encounter)
        await self.session.commit()
        await self.session.refresh(patient)
        await self.session.refresh(encounter)

        return TraumaIntakeResponse(
            patient_id=patient.id or patient_id,
            encounter_id=encounter.id or encounter_id,
            alias=alias,
            is_unidentified=True,
            status="active",
            created_at=now,
        )


    async def reconcile_identity(self, payload: ReconcileIdentityRequest) -> ReconcileIdentityResponse:
        """Atomically merge a shadow trauma patient's clinical records into a confirmed master patient."""
        trauma_patient = await self.session.get(Patient, payload.trauma_patient_id)
        if trauma_patient is None:
            raise HTTPException(404, "trauma patient record not found")

        master_patient = await self.session.get(Patient, payload.target_master_patient_id)
        if master_patient is None:
            raise HTTPException(404, "target master patient record not found")

        if trauma_patient.id == master_patient.id:
            raise HTTPException(400, "cannot merge a patient into themselves")

        # Find all encounters belonging to the shadow trauma patient
        encounters = list(
            (
                await self.session.scalars(
                    select(Encounter).where(Encounter.patient_id == payload.trauma_patient_id)
                )
            ).all()
        )

        now = datetime.now(UTC)
        encounter_count = len(encounters)
        vitals_count = 0
        interviews_count = 0
        assessments_count = 0
        decisions_count = 0

        # Re-parent all encounters and count linked clinical observations
        for encounter in encounters:
            encounter.patient_id = master_patient.id
            encounter.presenting_details = (
                f"{encounter.presenting_details or ''} [Reconciled from shadow identity {trauma_patient.first_name} "
                f"at {now.isoformat()}: {payload.reason}]"
            )

            # Count clinical records for audit transparency
            v_count = await self.session.scalar(
                select(VitalObservation).where(VitalObservation.encounter_id == encounter.id)
            )
            if v_count:
                vitals_count += 1

            i_count = await self.session.scalar(
                select(SymptomInterview).where(SymptomInterview.encounter_id == encounter.id)
            )
            if i_count:
                interviews_count += 1

            a_count = await self.session.scalar(
                select(TriageAssessment).where(TriageAssessment.encounter_id == encounter.id)
            )
            if a_count:
                assessments_count += 1

            d_count = await self.session.scalar(
                select(ClinicianDecision).where(ClinicianDecision.assessment_id.in_(
                    select(TriageAssessment.id).where(TriageAssessment.encounter_id == encounter.id)
                ))
            )
            if d_count:
                decisions_count += 1

        # Mark the shadow trauma patient record as merged
        trauma_patient.status = "merged"
        await self.session.commit()

        return ReconcileIdentityResponse(
            success=True,
            trauma_patient_id=payload.trauma_patient_id,
            target_master_patient_id=payload.target_master_patient_id,
            reparented_encounters_count=encounter_count,
            reparented_vitals_count=vitals_count,
            reparented_interviews_count=interviews_count,
            reparented_assessments_count=assessments_count,
            reparented_decisions_count=decisions_count,
            merged_at=now,
        )
