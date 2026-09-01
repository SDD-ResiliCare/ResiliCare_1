from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterParticipant
from src.db.models.triage import SymptomInterview, SymptomResponse, VitalObservation
from src.db.repositories.base import Repository


class EncounterRepository(Repository[Encounter]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Encounter)


class EncounterParticipantRepository(Repository[EncounterParticipant]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, EncounterParticipant)

    async def active_primary_doctor(
        self, encounter_id: UUID, *, for_update: bool = False
    ) -> EncounterParticipant | None:
        statement = select(EncounterParticipant).where(
            EncounterParticipant.encounter_id == encounter_id,
            EncounterParticipant.role == "primary_doctor",
            EncounterParticipant.ended_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)


class VitalObservationRepository(Repository[VitalObservation]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, VitalObservation)


class SymptomInterviewRepository(Repository[SymptomInterview]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SymptomInterview)


class SymptomResponseRepository(Repository[SymptomResponse]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SymptomResponse)
