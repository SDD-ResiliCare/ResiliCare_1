from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.billing import Invoice, InvoiceItem, Payment
from src.db.models.encounter import (
    DoctorWorkItem,
    Encounter,
    EncounterLocationHistory,
    EncounterParticipant,
    Queue,
    QueueEntry,
)
from src.db.models.medication import Prescription, PrescriptionItem
from src.db.models.organization import EsiCareAreaRule, Hospital, Ward
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
from src.db.models.workforce import Staff, StaffWardAssignment
from src.db.repositories.encounters import (
    EncounterParticipantRepository,
    EncounterRepository,
    SymptomInterviewRepository,
    SymptomResponseRepository,
    VitalObservationRepository,
)
from src.schemas.encounter import (
    DoctorTransferCreate,
    EncounterAllocationCreate,
    EncounterClosureCreate,
    EncounterCreate,
    EncounterDiagnosisCreate,
    EncounterUpdate,
    ParticipantCreate,
    VitalObservationCreate,
)
from src.schemas.triage import SymptomInterviewCreate, SymptomResponseCreate
from src.services.audit_service import record_audit_event
from src.services.doctor_work_service import DoctorWorkService


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
        current_doctor = next(
            (item for item in participants if item.role == "primary_doctor" and item.ended_at is None), None
        )
        current_doctor_staff = await self.session.get(Staff, current_doctor.staff_id) if current_doctor else None
        hospital = await self.session.get(Hospital, encounter.hospital_id)
        current_ward = (
            await self.session.get(Ward, encounter.current_ward_id) if encounter.current_ward_id is not None else None
        )
        active_location = await self.session.scalar(
            select(EncounterLocationHistory)
            .where(
                EncounterLocationHistory.encounter_id == encounter_id,
                EncounterLocationHistory.exited_at.is_(None),
            )
            .order_by(EncounterLocationHistory.entered_at.desc())
            .limit(1)
        )
        queue_entry = await self.session.scalar(
            select(QueueEntry).where(QueueEntry.encounter_id == encounter_id, QueueEntry.exited_at.is_(None))
        )
        doctor_work_item = await self.session.scalar(
            select(DoctorWorkItem).where(
                DoctorWorkItem.encounter_id == encounter_id,
                DoctorWorkItem.status.in_(("waiting", "in_service")),
            )
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
            "hospital": hospital,
            "current_ward": current_ward,
            "active_location": active_location,
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
            "current_doctor": current_doctor,
            "current_doctor_staff": current_doctor_staff,
            "queue_entry": queue_entry,
            "doctor_work_item": doctor_work_item,
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
        if payload.role == "primary_doctor":
            raise HTTPException(409, "primary doctors must be assigned through allocation or doctor transfer")
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
        encounter = await self.get(encounter_id, for_update=True)
        if assigned_by is None:
            raise HTTPException(403, "staff identity is required")
        if encounter.current_ward_id is None:
            raise HTTPException(409, "encounter must have a current ward before doctor transfer")
        current = await self.participants.active_primary_doctor(encounter_id, for_update=True)
        if current is None:
            raise HTTPException(409, "encounter has no active primary doctor")
        if current.staff_id == payload.new_doctor_staff_id:
            raise HTTPException(409, "new doctor is already the active primary doctor")
        new_doctor = await self.session.scalar(
            select(Staff)
            .where(
                Staff.id == payload.new_doctor_staff_id,
                Staff.hospital_id == encounter.hospital_id,
                Staff.staff_type == "doctor",
                Staff.employment_status == "active",
            )
            .with_for_update()
        )
        if new_doctor is None:
            raise HTTPException(404, "active replacement doctor not found in encounter hospital")
        ward_assignment = await self.session.scalar(
            select(StaffWardAssignment).where(
                StaffWardAssignment.staff_id == new_doctor.id,
                StaffWardAssignment.ward_id == encounter.current_ward_id,
                StaffWardAssignment.assigned_from <= payload.transferred_at,
                or_(
                    StaffWardAssignment.assigned_until.is_(None),
                    StaffWardAssignment.assigned_until > payload.transferred_at,
                ),
            )
        )
        if ward_assignment is None:
            raise HTTPException(422, "replacement doctor must be actively assigned to the encounter ward")
        work_item = await self.session.scalar(
            select(DoctorWorkItem)
            .where(
                DoctorWorkItem.encounter_id == encounter_id,
                DoctorWorkItem.status.in_(("waiting", "in_service")),
            )
            .with_for_update()
        )
        if work_item is None:
            raise HTTPException(409, "encounter has no active doctor work item")
        if payload.transferred_at < current.assigned_at or payload.transferred_at < work_item.queued_at:
            raise HTTPException(422, "doctor transfer cannot predate the active assignment")
        new_doctor_current = await self.session.scalar(
            select(DoctorWorkItem)
            .where(
                DoctorWorkItem.doctor_staff_id == new_doctor.id,
                DoctorWorkItem.status == "in_service",
            )
            .with_for_update()
        )

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
        was_in_service = work_item.status == "in_service"
        work_item.status = "transferred"
        work_item.end_reason = payload.reason
        work_item.completed_at = payload.transferred_at if was_in_service else None
        replacement_status = "waiting" if new_doctor_current is not None else "in_service"
        replacement_work = DoctorWorkItem(
            hospital_id=encounter.hospital_id,
            encounter_id=encounter_id,
            doctor_staff_id=new_doctor.id,
            ward_id=encounter.current_ward_id,
            status=replacement_status,
            priority_esi=work_item.priority_esi,
            queued_at=payload.transferred_at,
            started_at=payload.transferred_at if replacement_status == "in_service" else None,
            assigned_by_staff_id=assigned_by,
            allocation_reason=payload.reason,
        )
        self.session.add(replacement_work)
        if was_in_service:
            await DoctorWorkService(self.session).promote_next(current.staff_id, payload.transferred_at)
        encounter.status = "in_care" if replacement_status == "in_service" else "assigned"
        if replacement_status == "in_service":
            encounter.care_started_at = payload.transferred_at
        await self.session.commit()
        return replacement

    async def confirm_allocation(
        self,
        encounter_id: UUID,
        payload: EncounterAllocationCreate,
        *,
        confirmed_by_staff_id: UUID,
        actor_auth_user_id: UUID,
        hospital_id: UUID,
        request_id: str,
    ) -> dict:
        """Persist a post-triage ward, doctor, and doctor-queue allocation as one transaction."""
        encounter = await self.get(encounter_id, for_update=True)
        if encounter.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        if encounter.status in {"completed", "cancelled", "entered_in_error"}:
            raise HTTPException(409, "closed encounters cannot be allocated")

        queue_entry = await self.session.scalar(
            select(QueueEntry)
            .join(Queue, Queue.id == QueueEntry.queue_id)
            .where(
                QueueEntry.encounter_id == encounter_id,
                QueueEntry.exited_at.is_(None),
                Queue.hospital_id == hospital_id,
                Queue.status == "active",
            )
            .with_for_update()
        )
        if queue_entry is None:
            raise HTTPException(409, "encounter must be in the active hospital queue before allocation")

        assessment = await self.session.scalar(
            select(TriageAssessment)
            .where(TriageAssessment.encounter_id == encounter_id)
            .order_by(TriageAssessment.assessment_number.desc())
            .limit(1)
        )
        if assessment is None:
            raise HTTPException(409, "triage assessment is required before allocation")
        decision = await self.session.scalar(
            select(ClinicianDecision)
            .where(
                ClinicianDecision.assessment_id == assessment.id,
                ClinicianDecision.superseded_at.is_(None),
            )
            .order_by(ClinicianDecision.decided_at.desc())
            .limit(1)
        )
        if decision is None or assessment.assessment_status not in {"confirmed", "overridden"}:
            raise HTTPException(409, "the latest triage assessment must be clinician-confirmed before allocation")
        if payload.confirmed_at < decision.decided_at:
            raise HTTPException(422, "allocation confirmation cannot predate the triage decision")

        ward = await self.session.scalar(
            select(Ward).where(Ward.id == payload.ward_id, Ward.hospital_id == hospital_id, Ward.status == "active")
        )
        if ward is None:
            raise HTTPException(404, "active ward not found in encounter hospital")
        doctor = await self.session.scalar(
            select(Staff).where(
                Staff.id == payload.doctor_staff_id,
                Staff.hospital_id == hospital_id,
                Staff.staff_type == "doctor",
                Staff.employment_status == "active",
            ).with_for_update()
        )
        if doctor is None:
            raise HTTPException(404, "active doctor not found in encounter hospital")
        doctor_ward_assignment = await self.session.scalar(
            select(StaffWardAssignment).where(
                StaffWardAssignment.staff_id == doctor.id,
                StaffWardAssignment.ward_id == ward.id,
                StaffWardAssignment.assigned_from <= payload.confirmed_at,
                or_(
                    StaffWardAssignment.assigned_until.is_(None),
                    StaffWardAssignment.assigned_until > payload.confirmed_at,
                ),
            )
        )
        if doctor_ward_assignment is None:
            raise HTTPException(422, "doctor must have an active assignment to the selected ward")

        current_doctor_work = await self.session.scalar(
            select(DoctorWorkItem)
            .where(
                DoctorWorkItem.doctor_staff_id == doctor.id,
                DoctorWorkItem.status == "in_service",
            )
            .with_for_update()
        )

        suggested_rule = await self.session.scalar(
            select(EsiCareAreaRule)
            .where(
                EsiCareAreaRule.operational_config_id == assessment.operational_config_id,
                EsiCareAreaRule.esi_level == decision.final_esi,
            )
            .order_by(EsiCareAreaRule.is_default.desc(), EsiCareAreaRule.priority)
            .limit(1)
        )

        current_location = await self.session.scalar(
            select(EncounterLocationHistory)
            .where(
                EncounterLocationHistory.encounter_id == encounter_id,
                EncounterLocationHistory.exited_at.is_(None),
            )
            .order_by(EncounterLocationHistory.entered_at.desc())
            .with_for_update()
            .limit(1)
        )
        if current_location is not None and current_location.entered_at > payload.confirmed_at:
            raise HTTPException(422, "allocation confirmation cannot predate the current ward assignment")
        if current_location is not None and (
            current_location.ward_id != ward.id or current_location.bed_label != payload.bed_label
        ):
            current_location.exited_at = payload.confirmed_at
            current_location.transfer_reason = payload.reason
            current_location = None
        if current_location is None:
            current_location = EncounterLocationHistory(
                encounter_id=encounter_id,
                ward_id=ward.id,
                bed_label=payload.bed_label,
                entered_at=payload.confirmed_at,
                moved_by_staff_id=confirmed_by_staff_id,
                transfer_reason=payload.reason,
            )
            self.session.add(current_location)
        encounter.current_ward_id = ward.id

        current_doctor = await self.participants.active_primary_doctor(encounter_id, for_update=True)
        if current_doctor is not None and current_doctor.assigned_at > payload.confirmed_at:
            raise HTTPException(422, "allocation confirmation cannot predate the current doctor assignment")
        if current_doctor is not None and current_doctor.staff_id != doctor.id:
            current_doctor.ended_at = payload.confirmed_at
            current_doctor.end_reason = payload.reason
            previous_doctor = current_doctor
            current_doctor = None
        else:
            previous_doctor = None
        if current_doctor is None:
            current_doctor = EncounterParticipant(
                encounter_id=encounter_id,
                staff_id=doctor.id,
                role="primary_doctor",
                assigned_at=payload.confirmed_at,
                assigned_by_staff_id=confirmed_by_staff_id,
                assignment_reason=payload.reason,
                transferred_from_participant_id=previous_doctor.id if previous_doctor else None,
            )
            self.session.add(current_doctor)

        work_status = "waiting" if current_doctor_work is not None else "in_service"
        doctor_work_item = DoctorWorkItem(
            hospital_id=hospital_id,
            encounter_id=encounter_id,
            doctor_staff_id=doctor.id,
            ward_id=ward.id,
            status=work_status,
            priority_esi=decision.final_esi,
            queued_at=payload.confirmed_at,
            started_at=payload.confirmed_at if work_status == "in_service" else None,
            assigned_by_staff_id=confirmed_by_staff_id,
            allocation_reason=payload.reason,
        )
        self.session.add(doctor_work_item)

        queue_entry.status = "completed"
        queue_entry.exited_at = payload.confirmed_at
        queue_entry.exit_reason = "allocated_to_doctor"
        if work_status == "in_service":
            encounter.status = "in_care"
            encounter.care_started_at = payload.confirmed_at
        else:
            encounter.status = "assigned"

        await self.session.flush()
        doctor_queue_position = None
        if work_status == "waiting":
            doctor_queue_position = await self.session.scalar(
                select(func.count())
                .select_from(DoctorWorkItem)
                .where(
                    DoctorWorkItem.doctor_staff_id == doctor.id,
                    DoctorWorkItem.status == "waiting",
                    or_(
                        DoctorWorkItem.priority_esi < doctor_work_item.priority_esi,
                        and_(
                            DoctorWorkItem.priority_esi == doctor_work_item.priority_esi,
                            DoctorWorkItem.queued_at <= doctor_work_item.queued_at,
                        ),
                    ),
                )
            )
        await record_audit_event(
            self.session,
            hospital_id=hospital_id,
            action="encounter.allocation_confirmed",
            resource_type="encounter",
            resource_id=encounter.id,
            request_id=request_id,
            actor_staff_id=confirmed_by_staff_id,
            actor_auth_user_id=actor_auth_user_id,
            metadata={
                "queue_entry_id": str(queue_entry.id),
                "triage_assessment_id": str(assessment.id),
                "clinician_decision_id": str(decision.id),
                "confirmed_esi": decision.final_esi,
                "ward_id": str(ward.id),
                "suggested_ward_id": str(suggested_rule.ward_id) if suggested_rule else None,
                "ward_matches_suggestion": suggested_rule is None or suggested_rule.ward_id == ward.id,
                "doctor_staff_id": str(doctor.id),
                "location_history_id": str(current_location.id),
                "doctor_participant_id": str(current_doctor.id),
                "doctor_work_item_id": str(doctor_work_item.id),
                "doctor_work_status": doctor_work_item.status,
                "doctor_queue_position": doctor_queue_position,
                "hospital_queue_status": queue_entry.status,
                "reason": payload.reason,
            },
        )
        await self.session.commit()
        return {
            "encounter_id": encounter.id,
            "hospital_id": hospital_id,
            "ward": {"id": ward.id, "ward_code": ward.ward_code, "name": ward.name, "ward_type": ward.ward_type},
            "primary_doctor": {
                "id": doctor.id,
                "employee_code": doctor.employee_code,
                "first_name": doctor.first_name,
                "last_name": doctor.last_name,
            },
            "location_history_id": current_location.id,
            "doctor_participant_id": current_doctor.id,
            "triage_assessment_id": assessment.id,
            "clinician_decision_id": decision.id,
            "hospital_queue_entry_id": queue_entry.id,
            "hospital_queue_status": queue_entry.status,
            "doctor_work_item_id": doctor_work_item.id,
            "doctor_work_status": doctor_work_item.status,
            "doctor_queue_position": doctor_queue_position,
            "confirmed_by_staff_id": confirmed_by_staff_id,
            "confirmed_at": payload.confirmed_at,
        }

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
        await DoctorWorkService(self.session).finish_encounter_work(
            encounter_id,
            payload.closed_at,
            f"Encounter closed: {payload.disposition}",
        )
        current_doctor = await self.participants.active_primary_doctor(encounter_id, for_update=True)
        if current_doctor is not None:
            current_doctor.ended_at = payload.closed_at
            current_doctor.end_reason = f"Encounter closed: {payload.disposition}"
        current_location = await self.session.scalar(
            select(EncounterLocationHistory)
            .where(
                EncounterLocationHistory.encounter_id == encounter_id,
                EncounterLocationHistory.exited_at.is_(None),
            )
            .with_for_update()
        )
        if current_location is not None:
            current_location.exited_at = payload.closed_at
            current_location.transfer_reason = f"Encounter closed: {payload.disposition}"
        encounter.status = "completed"
        encounter.completed_at = payload.closed_at
        encounter.current_ward_id = None
        await self.session.commit()
        await self.session.refresh(closure)
        return closure
