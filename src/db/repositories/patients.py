from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.patient import Patient, PatientIdentifier
from src.db.repositories.base import Repository


class PatientRepository(Repository[Patient]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Patient)


class PatientIdentifierRepository(Repository[PatientIdentifier]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PatientIdentifier)
