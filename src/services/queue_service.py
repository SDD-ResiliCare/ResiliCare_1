from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterLocationHistory, EncounterParticipant, Queue, QueueEntry
from src.db.models.organization import EsiCareAreaRule, Hospital, Ward
from src.db.models.patient import Patient
from src.db.models.triage import AssessmentSafetyAction, ClinicianDecision, TriageAssessment, VitalObservation
from src.db.models.workforce import Staff
from src.db.repositories.queues import QueueEntryRepository, QueueRepository
from src.schemas.encounter import QueueCreate, QueueEntryAction, QueueEntryCreate, QueuePriorityUpdate, QueueUpdate


class QueueService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.queues = QueueRepository(session)
        self.entries = QueueEntryRepository(session)

    async def create_queue(self, payload: QueueCreate) -> Queue:
        existing = await self.session.scalar(
            select(Queue).where(Queue.hospital_id == payload.hospital_id, Queue.status == "active")
        )
        if existing is not None:
            raise HTTPException(409, "hospital already has an active queue")
        queue = await self.queues.add(Queue(**payload.model_dump(), status="active"))
        await self.session.commit()
        return queue

    async def list_queues(self, hospital_id: UUID) -> list[Queue]:
        return list(
            (
                await self.session.scalars(
                    select(Queue).where(Queue.hospital_id == hospital_id).order_by(Queue.created_at.desc())
                )
            ).all()
        )

    async def update_queue(self, queue_id: UUID, payload: QueueUpdate, hospital_id: UUID) -> Queue:
        queue = await self.get_queue(queue_id)
        if queue.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(queue, key, value)
        await self.session.commit()
        return queue

    async def deactivate_queue(self, queue_id: UUID, hospital_id: UUID) -> Queue:
        queue = await self.get_queue(queue_id)
        if queue.hospital_id != hospital_id:
            raise HTTPException(403, "cross-hospital access is not allowed")
        active_entries = await self.session.scalar(
            select(func.count())
            .select_from(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.exited_at.is_(None))
        )
        if active_entries:
            raise HTTPException(409, "queue with active entries cannot be deactivated")
        queue.status = "inactive"
        await self.session.commit()
        return queue

    async def add_entry(self, queue_id: UUID, payload: QueueEntryCreate) -> QueueEntry:
        queue = await self.queues.get(queue_id)
        if queue is None:
            raise HTTPException(404, "queue not found")
        encounter = await self.session.get(Encounter, payload.encounter_id)
        if encounter is None or encounter.hospital_id != queue.hospital_id:
            raise HTTPException(404, "encounter not found in queue hospital")
        if encounter.status in {"completed", "cancelled", "entered_in_error"}:
            raise HTTPException(409, "closed encounters cannot enter a queue")
        entry = await self.entries.add(
            QueueEntry(
                queue_id=queue_id,
                encounter_id=payload.encounter_id,
                entered_at=payload.entered_at,
                status="waiting",
            )
        )
        await self.session.commit()
        return entry

    async def list_entries(self, queue_id: UUID) -> list[QueueEntry]:
        if await self.queues.get(queue_id) is None:
            raise HTTPException(404, "queue not found")
        statement = (
            select(QueueEntry)
            .where(QueueEntry.queue_id == queue_id, QueueEntry.exited_at.is_(None))
            .order_by(QueueEntry.priority_boost.desc(), QueueEntry.entered_at)
        )
        return list((await self.session.scalars(statement)).all())

    async def current_queue(self, hospital_id: UUID) -> Queue:
        queue = await self.session.scalar(
            select(Queue).where(Queue.hospital_id == hospital_id, Queue.status == "active")
        )
        if queue is None:
            raise HTTPException(404, "active hospital queue not found")
        return queue

    async def ranked_entries(self, queue: Queue) -> list[dict]:
        now = datetime.now(UTC)
        hospital = await self.session.get(Hospital, queue.hospital_id)
        if hospital is None:
            raise HTTPException(409, "queue hospital no longer exists")
        rows = (
            await self.session.execute(
                select(QueueEntry, Encounter, Patient)
                .join(Encounter, Encounter.id == QueueEntry.encounter_id)
                .join(Patient, Patient.id == Encounter.patient_id)
                .where(QueueEntry.queue_id == queue.id, QueueEntry.exited_at.is_(None))
            )
        ).all()
        ranked: list[dict] = []
        for entry, encounter, patient in rows:
            triage_row = (
                await self.session.execute(
                    select(TriageAssessment, ClinicianDecision)
                    .outerjoin(
                        ClinicianDecision,
                        and_(
                            ClinicianDecision.assessment_id == TriageAssessment.id,
                            ClinicianDecision.superseded_at.is_(None),
                        ),
                    )
                    .where(TriageAssessment.encounter_id == encounter.id)
                    .order_by(
                        TriageAssessment.assessment_number.desc(),
                        ClinicianDecision.decided_at.desc().nullslast(),
                    )
                    .limit(1)
                )
            ).first()
            assessment, decision = triage_row if triage_row else (None, None)
            effective_esi = decision.final_esi if decision else (assessment.recommended_esi if assessment else None)
            suggested_ward = None
            if assessment is not None and effective_esi is not None:
                suggested_rule = await self.session.scalar(
                    select(EsiCareAreaRule)
                    .where(
                        EsiCareAreaRule.operational_config_id == assessment.operational_config_id,
                        EsiCareAreaRule.esi_level == effective_esi,
                    )
                    .order_by(desc(EsiCareAreaRule.is_default), EsiCareAreaRule.priority)
                    .limit(1)
                )
                if suggested_rule is not None:
                    suggested_ward = await self.session.get(Ward, suggested_rule.ward_id)

            assigned_ward = (
                await self.session.get(Ward, encounter.current_ward_id) if encounter.current_ward_id is not None else None
            )
            doctor_row = (
                await self.session.execute(
                    select(EncounterParticipant, Staff)
                    .join(Staff, Staff.id == EncounterParticipant.staff_id)
                    .where(
                        EncounterParticipant.encounter_id == encounter.id,
                        EncounterParticipant.role == "primary_doctor",
                        EncounterParticipant.ended_at.is_(None),
                    )
                    .limit(1)
                )
            ).first()
            participant, doctor = doctor_row if doctor_row else (None, None)
            active_location = await self.session.scalar(
                select(EncounterLocationHistory)
                .where(
                    EncounterLocationHistory.encounter_id == encounter.id,
                    EncounterLocationHistory.exited_at.is_(None),
                )
                .order_by(EncounterLocationHistory.entered_at.desc())
                .limit(1)
            )
            active_boost = (
                entry.priority_boost
                if entry.priority_boost_expires_at is None or entry.priority_boost_expires_at > now
                else 0
            )
            reassessment_overdue = entry.reassessment_due_at is not None and entry.reassessment_due_at <= now
            safety_alert = bool(
                await self.session.scalar(
                    select(func.count())
                    .select_from(AssessmentSafetyAction)
                    .join(TriageAssessment, TriageAssessment.id == AssessmentSafetyAction.assessment_id)
                    .where(
                        TriageAssessment.encounter_id == encounter.id,
                        AssessmentSafetyAction.status == "pending",
                        AssessmentSafetyAction.severity == "mandatory",
                    )
                )
            )
            vitals = await self.session.scalar(
                select(VitalObservation)
                .where(VitalObservation.encounter_id == encounter.id)
                .order_by(VitalObservation.observed_at.desc())
                .limit(1)
            )
            ranked.append(
                {
                    "queue_entry_id": entry.id,
                    "queue_entry": entry,
                    "queue_status": entry.status,
                    "entered_at": entry.entered_at,
                    "called_at": entry.called_at,
                    "reassessment_due_at": entry.reassessment_due_at,
                    "reassessment_overdue": reassessment_overdue,
                    "active_priority_boost": active_boost,
                    "patient": patient,
                    "encounter": encounter,
                    "final_esi": decision.final_esi if decision else None,
                    "safety_alert": safety_alert,
                    "vitals": {k.name: getattr(vitals, k.name) for k in vitals.__table__.columns} if vitals else None,
                    "triage": {
                        "assessment_id": assessment.id if assessment else None,
                        "assessment_status": assessment.assessment_status if assessment else None,
                        "predicted_esi": assessment.recommended_esi if assessment else None,
                        "possible_esi_levels": assessment.possible_esi_levels if assessment else [],
                        "uncertainty_label": assessment.uncertainty_label if assessment else None,
                        "requires_senior_review": assessment.requires_senior_review if assessment else False,
                        "safety_alert": safety_alert,
                        "confirmation_status": (
                            decision.decision_type if decision else ("pending" if assessment else "not_assessed")
                        ),
                        "decision_id": decision.id if decision else None,
                        "final_esi": decision.final_esi if decision else None,
                        "decided_at": decision.decided_at if decision else None,
                        "ai_overview": assessment.ai_overview if assessment else None,
                        "ai_overview_factors": assessment.ai_overview_factors if assessment else {},
                    },
                    "allocation": {
                        "hospital_id": hospital.id,
                        "hospital_name": hospital.name,
                        "suggested_ward": self._ward_summary(suggested_ward),
                        "suggestion_basis": (
                            "confirmed_esi" if decision else ("predicted_esi" if assessment else None)
                        ),
                        "assigned_ward": self._ward_summary(assigned_ward),
                        "primary_doctor": self._doctor_summary(doctor),
                        "assigned_by_staff_id": (
                            active_location.moved_by_staff_id
                            if active_location
                            else (participant.assigned_by_staff_id if participant else None)
                        ),
                        "assigned_at": (
                            active_location.entered_at
                            if active_location
                            else (participant.assigned_at if participant else None)
                        ),
                        "allocation_overview": None,
                    },
                    "effective_esi": effective_esi,
                }
            )
        ranked.sort(
            key=lambda item: (
                item["effective_esi"] if item["effective_esi"] is not None else 6,
                not item["triage"]["safety_alert"],
                not item["reassessment_overdue"],
                -item["active_priority_boost"],
                item["entered_at"],
            )
        )
        for rank, item in enumerate(ranked, 1):
            item["rank"] = rank
            item.pop("effective_esi")
        return ranked

    @staticmethod
    def _ward_summary(ward: Ward | None) -> dict | None:
        if ward is None:
            return None
        return {"id": ward.id, "ward_code": ward.ward_code, "name": ward.name, "ward_type": ward.ward_type}

    @staticmethod
    def _doctor_summary(doctor: Staff | None) -> dict | None:
        if doctor is None:
            return None
        return {
            "id": doctor.id,
            "employee_code": doctor.employee_code,
            "first_name": doctor.first_name,
            "last_name": doctor.last_name,
        }

    async def get_entry_for_hospital(
        self, entry_id: UUID, hospital_id: UUID, *, for_update: bool = False
    ) -> QueueEntry:
        statement = (
            select(QueueEntry)
            .join(Queue, Queue.id == QueueEntry.queue_id)
            .where(QueueEntry.id == entry_id, Queue.hospital_id == hospital_id)
        )
        if for_update:
            statement = statement.with_for_update()
        entry = await self.session.scalar(statement)
        if entry is None:
            raise HTTPException(404, "queue entry not found")
        return entry

    async def update_priority(
        self, entry_id: UUID, payload: QueuePriorityUpdate, staff_id: UUID, hospital_id: UUID
    ) -> QueueEntry:
        entry = await self.get_entry_for_hospital(entry_id, hospital_id, for_update=True)
        if entry.exited_at is not None:
            raise HTTPException(409, "completed queue entry cannot be reprioritized")
        entry.priority_boost = payload.priority_boost
        entry.priority_boost_reason = payload.reason
        entry.priority_boost_expires_at = payload.expires_at
        entry.boosted_by_staff_id = staff_id if payload.priority_boost else None
        await self.session.commit()
        return entry

    async def transition(self, entry_id: UUID, action: str, payload: QueueEntryAction, hospital_id: UUID) -> QueueEntry:
        entry = await self.get_entry_for_hospital(entry_id, hospital_id, for_update=True)
        if entry.exited_at is not None:
            raise HTTPException(409, "queue entry is already closed")
        encounter = await self.session.get(Encounter, entry.encounter_id, with_for_update=True)
        if action == "call":
            entry.status = "called"
            entry.called_at = payload.occurred_at
        elif action == "start-care":
            entry.status = "in_service"
            if encounter:
                encounter.status = "in_care"
                encounter.care_started_at = payload.occurred_at
        elif action in {"exit", "cancel"}:
            entry.status = "completed" if action == "exit" else "cancelled"
            entry.exited_at = payload.occurred_at
            entry.exit_reason = payload.reason
        else:
            raise HTTPException(422, "unknown queue action")
        await self.session.commit()
        return entry

    async def get_queue(self, queue_id: UUID):
        queue = await self.queues.get(queue_id)
        if queue is None:
            raise HTTPException(404, "queue not found")
        return queue
