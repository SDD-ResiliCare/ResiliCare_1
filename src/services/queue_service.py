from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, Queue, QueueEntry
from src.db.models.patient import Patient
from src.db.models.triage import AssessmentSafetyAction, ClinicianDecision, TriageAssessment
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
            final_esi = await self.session.scalar(
                select(ClinicianDecision.final_esi)
                .join(TriageAssessment, TriageAssessment.id == ClinicianDecision.assessment_id)
                .where(TriageAssessment.encounter_id == encounter.id, ClinicianDecision.superseded_at.is_(None))
                .order_by(ClinicianDecision.decided_at.desc())
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
            ranked.append(
                {
                    "queue_entry": entry,
                    "encounter": encounter,
                    "patient": patient,
                    "final_esi": final_esi,
                    "reassessment_overdue": reassessment_overdue,
                    "safety_alert": safety_alert,
                    "active_priority_boost": active_boost,
                }
            )
        ranked.sort(
            key=lambda item: (
                item["final_esi"] if item["final_esi"] is not None else 6,
                not item["safety_alert"],
                not item["reassessment_overdue"],
                -item["active_priority_boost"],
                item["queue_entry"].entered_at,
            )
        )
        for rank, item in enumerate(ranked, 1):
            item["rank"] = rank
        return ranked

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
