from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.medication import Prescription, PrescriptionItem
from src.db.repositories.base import Repository


class PrescriptionRepository(Repository[Prescription]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Prescription)


class PrescriptionItemRepository(Repository[PrescriptionItem]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PrescriptionItem)
