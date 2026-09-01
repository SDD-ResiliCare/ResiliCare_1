from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.billing import Invoice, InvoiceItem, Payment
from src.db.models.encounter import Encounter, EncounterParticipant, QueueEntry
from src.db.models.medication import Prescription, PrescriptionItem
from src.db.models.patient import Patient, PatientAllergy, PatientCondition
from src.db.models.triage import (
    AssessmentSafetyAction,
    ClinicianDecision,
    EncounterClosure,
    EncounterDiagnosis,
    SymptomInterview,
    SymptomResponse,
    TriageAssessment,
    VitalObservation,
)
from src.db.repositories.encounters import (
    EncounterParticipantRepository,
    EncounterRepository,
    SymptomInterviewRepository,
    SymptomResponseRepository,
    VitalObservationRepository,
)
from src.schemas.encounter import (
    DoctorTransferCreate,
    EncounterClosureCreate,
    EncounterCreate,
    EncounterDiagnosisCreate,
    EncounterUpdate,
    ParticipantCreate,
    VitalObservationCreate,
)
from src.schemas.triage import SymptomInterviewCreate, SymptomResponseCreate


class EncounterService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.encounters = EncounterRepository(session)
        self.participants = EncounterParticipantRepository(session)
        self.vitals = VitalObservationRepository(session)
        self.interviews = SymptomInterviewRepository(session)
        self.responses = SymptomResponseRepository(session)

    async def create(self, payload: EncounterCreate) -> Encounter:
        encounter = await self.encounters.add(Encounter(**payload.model_dump(), status="arrived"))
        await self.session.commit()
        return encounter

    async def get(self, encounter_id: UUID, *, for_update: bool = False) -> Encounter:
        encounter = await self.encounters.get(encounter_id, for_update=for_update)
        if encounter is None:
            raise HTTPException(404, "encounter not found")
        return encounter

    async def list(
        self,
        hospital_id: UUID,
        *,
        status: str | None,
        patient_id: UUID | None,
        doctor_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Encounter], int]:
        statement = select(Encounter).where(Encounter.hospital_id == hospital_id)
        count_statement = select(func.count(func.distinct(Encounter.id))).where(Encounter.hospital_id == hospital_id)
        if doctor_id:
            join_condition = EncounterParticipant.encounter_id == Encounter.id
            statement = statement.join(EncounterParticipant, join_condition).where(
                EncounterParticipant.staff_id == doctor_id,
                EncounterParticipant.role == "primary_doctor",
                EncounterParticipant.ended_at.is_(None),
            )
            count_statement = count_statement.join(EncounterParticipant, join_condition).where(
                EncounterParticipant.staff_id == doctor_id,
                EncounterParticipant.role == "primary_doctor",
                EncounterParticipant.ended_at.is_(None),
            )
        if status:
            statement = statement.where(Encounter.status == status)
            count_statement = count_statement.where(Encounter.status == status)
        if patient_id:
            statement = statement.where(Encounter.patient_id == patient_id)
            count_statement = count_statement.where(Encounter.patient_id == patient_id)
        statement = statement.distinct().order_by(Encounter.arrived_at.desc())
        items = list((await self.session.scalars(statement.limit(page_size).offset((page - 1) * page_size))).all())
        total = await self.session.scalar(count_statement) or 0
        return items, total

    async def update(self, encounter_id: UUID, payload: EncounterUpdate) -> Encounter:
        encounter = await self.get(encounter_id)
        if encounter.status in {"completed", "entered_in_error"}:
            raise HTTPException(409, "closed encounters cannot be edited")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(encounter, key, value)
        await self.session.commit()
        await self.session.refresh(encounter)
        return encounter

    async def mark_entered_in_error(self, encounter_id: UUID, reason: str) -> Encounter:
        encounter = await self.get(encounter_id, for_update=True)
        encounter.status = "entered_in_error"
        encounter.data_quality_notes = f"{encounter.data_quality_notes or ''}\nEntered in error: {reason}".strip()
        await self.session.commit()
        return encounter

    async def workspace(self, encounter_id: UUID) -> dict:
        encounter = await self.get(encounter_id)
        patient = await self.session.get(Patient, encounter.patient_id)
        participants = list(
            (
                await self.session.scalars(
                    select(EncounterParticipant)
                    .where(EncounterParticipant.encounter_id == encounter_id)
                    .order_by(EncounterParticipant.assigned_at)
                )
            ).all()
        )
        queue_entry = await self.session.scalar(
            select(QueueEntry).where(QueueEntry.encounter_id == encounter_id, QueueEntry.exited_at.is_(None))
        )
        vitals = list(
            (
                await self.session.scalars(
                    select(VitalObservation)
                    .where(VitalObservation.encounter_id == encounter_id)
                    .order_by(VitalObservation.observed_at.desc())
                )
            ).all()
        )
        interviews = list(
            (
                await self.session.scalars(
                    select(SymptomInterview)
                    .where(SymptomInterview.encounter_id == encounter_id)
                    .order_by(SymptomInterview.interview_number)
                )
            ).all()
        )
        interview_ids = [item.id for item in interviews]
        responses = (
            list(
                (
                    await self.session.scalars(
                        select(SymptomResponse)
                        .where(SymptomResponse.interview_id.in_(interview_ids))
                        .order_by(SymptomResponse.answered_at)
                    )
                ).all()
            )
            if interview_ids
            else []
        )
        assessments = list(
            (
                await self.session.scalars(
                    select(TriageAssessment)
                    .where(TriageAssessment.encounter_id == encounter_id)
                    .order_by(TriageAssessment.assessment_number.desc())
                )
            ).all()
        )
        assessment_ids = [item.id for item in assessments]
        decisions = (
            list(
                (
                    await self.session.scalars(
                        select(ClinicianDecision).where(ClinicianDecision.assessment_id.in_(assessment_ids))
                    )
                ).all()
            )
            if assessment_ids
            else []
        )
        safety_actions = (
            list(
                (
                    await self.session.scalars(
                        select(AssessmentSafetyAction).where(AssessmentSafetyAction.assessment_id.in_(assessment_ids))
                    )
                ).all()
            )
            if assessment_ids
            else []
        )
        diagnoses = list(
            (
                await self.session.scalars(
                    select(EncounterDiagnosis).where(EncounterDiagnosis.encounter_id == encounter_id)
                )
            ).all()
        )
        closure = await self.session.scalar(
            select(EncounterClosure).where(EncounterClosure.encounter_id == encounter_id)
        )
        prescriptions = list(
            (await self.session.scalars(select(Prescription).where(Prescription.encounter_id == encounter_id))).all()
        )
        prescription_ids = [item.id for item in prescriptions]
        prescription_items = (
            list(
                (
                    await self.session.scalars(
                        select(PrescriptionItem).where(PrescriptionItem.prescription_id.in_(prescription_ids))
                    )
                ).all()
            )
            if prescription_ids
            else []
        )
        invoices = list((await self.session.scalars(select(Invoice).where(Invoice.encounter_id == encounter_id))).all())
        invoice_ids = [item.id for item in invoices]
        invoice_items = (
            list((await self.session.scalars(select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids)))).all())
            if invoice_ids
            else []
        )
        payments = (
            list((await self.session.scalars(select(Payment).where(Payment.invoice_id.in_(invoice_ids)))).all())
            if invoice_ids
            else []
        )
        return {
            "encounter": encounter,
            "patient": patient,
            "allergies": list(
                (
                    await self.session.scalars(
                        select(PatientAllergy).where(PatientAllergy.patient_id == encounter.patient_id)
                    )
                ).all()
            ),
            "conditions": list(
                (
                    await self.session.scalars(
                        select(PatientCondition).where(PatientCondition.patient_id == encounter.patient_id)
                    )
                ).all()
            ),
            "participants": participants,
            "current_doctor": next(
                (item for item in participants if item.role == "primary_doctor" and item.ended_at is None), None
            ),
            "queue_entry": queue_entry,
            "latest_vitals": vitals[0] if vitals else None,
            "vitals": vitals,
            "interviews": interviews,
            "symptom_responses": responses,
            "latest_assessment": assessments[0] if assessments else None,
            "assessments": assessments,
            "clinician_decisions": decisions,
            "safety_actions": safety_actions,
            "diagnoses": diagnoses,
            "prescriptions": prescriptions,
            "prescription_items": prescription_items,
            "invoices": invoices,
            "invoice_items": invoice_items,
            "payments": payments,
            "closure": closure,
        }

    async def add_participant(
        self, encounter_id: UUID, payload: ParticipantCreate, assigned_by: UUID | None
    ) -> EncounterParticipant:
        await self.get(encounter_id)
        if payload.role == "primary_doctor" and await self.participants.active_primary_doctor(encounter_id):
            raise HTTPException(409, "encounter already has an active primary doctor; use doctor transfer")
        participant = await self.participants.add(
            EncounterParticipant(
                encounter_id=encounter_id,
                assigned_by_staff_id=assigned_by,
                **payload.model_dump(),
            )
        )
        await self.session.commit()
        return participant

    async def transfer_doctor(
        self, encounter_id: UUID, payload: DoctorTransferCreate, assigned_by: UUID | None
    ) -> EncounterParticipant:
        await self.get(encounter_id, for_update=True)
        current = await self.participants.active_primary_doctor(encounter_id, for_update=True)
        if current is None:
            raise HTTPException(409, "encounter has no active primary doctor")
        if current.staff_id == payload.new_doctor_staff_id:
            raise HTTPException(409, "new doctor is already the active primary doctor")
        current.ended_at = payload.transferred_at
        current.end_reason = payload.reason
        replacement = await self.participants.add(
            EncounterParticipant(
                encounter_id=encounter_id,
                staff_id=payload.new_doctor_staff_id,
                role="primary_doctor",
                assigned_at=payload.transferred_at,
                assigned_by_staff_id=assigned_by,
                assignment_reason=payload.reason,
                transferred_from_participant_id=current.id,
            )
        )
        await self.session.commit()
        return replacement

    async def record_vitals(self, encounter_id: UUID, payload: VitalObservationCreate) -> VitalObservation:
        await self.get(encounter_id)
        values = payload.model_dump()
        if payload.gcs_eye is not None and payload.gcs_verbal is not None and payload.gcs_motor is not None:
            values["gcs_total"] = payload.gcs_eye + payload.gcs_verbal + payload.gcs_motor
        else:
            values["gcs_total"] = None
        observation = await self.vitals.add(VitalObservation(encounter_id=encounter_id, **values))
        await self.session.commit()
        return observation

    async def start_interview(self, encounter_id: UUID, payload: SymptomInterviewCreate) -> SymptomInterview:
        await self.get(encounter_id)
        next_number = (
            await self.session.scalar(
                select(func.coalesce(func.max(SymptomInterview.interview_number), 0) + 1).where(
                    SymptomInterview.encounter_id == encounter_id
                )
            )
        ) or 1
        interview = await self.interviews.add(
            SymptomInterview(
                encounter_id=encounter_id,
                interview_number=next_number,
                status="in_progress",
                **payload.model_dump(),
            )
        )
        await self.session.commit()
        return interview

    async def record_response(
        self, interview_id: UUID, payload: SymptomResponseCreate, hospital_id: UUID | None
    ) -> SymptomResponse:
        interview = await self.interviews.get(interview_id)
        if interview is None:
            raise HTTPException(404, "symptom interview not found")
        encounter = await self.get(interview.encounter_id)
        if hospital_id is not None and encounter.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        if interview.status != "in_progress":
            raise HTTPException(409, "symptom interview is not open")
        response = await self.responses.add(SymptomResponse(interview_id=interview_id, **payload.model_dump()))
        await self.session.commit()
        return response

    async def add_diagnosis(
        self, encounter_id: UUID, payload: EncounterDiagnosisCreate, staff_id: UUID
    ) -> EncounterDiagnosis:
        await self.get(encounter_id)
        diagnosis = EncounterDiagnosis(
            encounter_id=encounter_id, diagnosed_by_staff_id=staff_id, **payload.model_dump()
        )
        self.session.add(diagnosis)
        await self.session.commit()
        await self.session.refresh(diagnosis)
        return diagnosis

    async def close_encounter(
        self, encounter_id: UUID, payload: EncounterClosureCreate, staff_id: UUID
    ) -> EncounterClosure:
        encounter = await self.get(encounter_id, for_update=True)
        if encounter.completed_at is not None:
            raise HTTPException(409, "encounter is already closed")
        closure = EncounterClosure(encounter_id=encounter_id, closed_by_staff_id=staff_id, **payload.model_dump())
        self.session.add(closure)
        encounter.status = "completed"
        encounter.completed_at = payload.closed_at
        await self.session.commit()
        await self.session.refresh(closure)
        return closure
