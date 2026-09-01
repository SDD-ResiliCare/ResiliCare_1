from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.triage import AssessmentSafetyAction, ClinicianDecision, TriageAssessment
from src.db.repositories.base import Repository


class TriageAssessmentRepository(Repository[TriageAssessment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, TriageAssessment)


class ClinicianDecisionRepository(Repository[ClinicianDecision]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, ClinicianDecision)


class SafetyActionRepository(Repository[AssessmentSafetyAction]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AssessmentSafetyAction)
