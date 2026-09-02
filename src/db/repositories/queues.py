from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Queue, QueueEntry
from src.db.repositories.base import Repository


class QueueRepository(Repository[Queue]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Queue)


class QueueEntryRepository(Repository[QueueEntry]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, QueueEntry)
