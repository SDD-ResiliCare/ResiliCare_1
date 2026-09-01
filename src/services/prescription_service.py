from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import EncounterParticipant
from src.db.models.medication import Prescription, PrescriptionItem
from src.db.repositories.prescriptions import PrescriptionItemRepository, PrescriptionRepository
from src.schemas.prescription import PrescriptionCreate


class PrescriptionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.prescriptions = PrescriptionRepository(session)
        self.items = PrescriptionItemRepository(session)

    async def create(
        self, encounter_id: UUID, payload: PrescriptionCreate, staff_id: UUID, hospital_id: UUID
    ) -> Prescription:
        participant = await self.session.scalar(
            select(EncounterParticipant).where(
                EncounterParticipant.id == payload.prescriber_participant_id,
                EncounterParticipant.encounter_id == encounter_id,
                EncounterParticipant.role == "primary_doctor",
                EncounterParticipant.staff_id == staff_id,
            )
        )
        if participant is None:
            raise HTTPException(422, "prescriber must be a primary doctor assigned to this encounter")
        from src.db.models.encounter import Encounter

        if (
            await self.session.scalar(
                select(Encounter.id).where(Encounter.id == encounter_id, Encounter.hospital_id == hospital_id)
            )
            is None
        ):
            raise HTTPException(403, "cross-hospital access is not allowed")
        values = payload.model_dump(exclude={"items"})
        prescription = await self.prescriptions.add(
            Prescription(
                encounter_id=encounter_id,
                status="draft",
                revision_number=1,
                **values,
            )
        )
        for item in payload.items:
            await self.items.add(PrescriptionItem(prescription_id=prescription.id, **item.model_dump()))
        await self.session.commit()
        return prescription
