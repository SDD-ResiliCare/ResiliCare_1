from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.workforce import ClinicalStaffProfile, Staff, StaffWardAssignment
from src.db.repositories.base import Repository


class StaffRepository(Repository[Staff]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Staff)


class ClinicalStaffProfileRepository(Repository[ClinicalStaffProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ClinicalStaffProfile)


class StaffWardAssignmentRepository(Repository[StaffWardAssignment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, StaffWardAssignment)
