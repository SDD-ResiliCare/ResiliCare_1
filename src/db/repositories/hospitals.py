from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.organization import Hospital, Ward
from src.db.repositories.base import Repository


class HospitalRepository(Repository[Hospital]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Hospital)


class WardRepository(Repository[Ward]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Ward)
