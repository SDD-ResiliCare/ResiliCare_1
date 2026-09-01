from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Queue, QueueEntry
from src.db.repositories.queues import QueueEntryRepository, QueueRepository
from src.schemas.encounter import QueueCreate, QueueEntryCreate


class QueueService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.queues = QueueRepository(session)
        self.entries = QueueEntryRepository(session)

    async def create_queue(self, payload: QueueCreate) -> Queue:
        queue = await self.queues.add(Queue(**payload.model_dump(), status="active"))
        await self.session.commit()
        return queue

    async def add_entry(self, queue_id: UUID, payload: QueueEntryCreate) -> QueueEntry:
        if await self.queues.get(queue_id) is None:
            raise HTTPException(404, "queue not found")
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

    async def get_queue(self, queue_id: UUID):
        queue = await self.queues.get(queue_id)
        if queue is None:
            raise HTTPException(404, "queue not found")
        return queue
