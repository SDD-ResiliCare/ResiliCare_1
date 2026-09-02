from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter, EncounterParticipant
from src.db.models.medication import Prescription, PrescriptionItem
from src.db.repositories.prescriptions import PrescriptionItemRepository, PrescriptionRepository
from src.schemas.prescription import PrescriptionCancel, PrescriptionCreate, PrescriptionDraftUpdate, PrescriptionIssue


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

    async def get(self, prescription_id: UUID, hospital_id: UUID, *, for_update: bool = False) -> Prescription:
        statement = (
            select(Prescription)
            .join(Encounter, Encounter.id == Prescription.encounter_id)
            .where(Prescription.id == prescription_id, Encounter.hospital_id == hospital_id)
        )
        if for_update:
            statement = statement.with_for_update()
        prescription = await self.session.scalar(statement)
        if prescription is None:
            raise HTTPException(404, "prescription not found")
        return prescription

    async def list_for_encounter(self, encounter_id: UUID, hospital_id: UUID) -> list[Prescription]:
        if (
            await self.session.scalar(
                select(Encounter.id).where(Encounter.id == encounter_id, Encounter.hospital_id == hospital_id)
            )
            is None
        ):
            raise HTTPException(404, "encounter not found")
        return list(
            (
                await self.session.scalars(
                    select(Prescription)
                    .where(Prescription.encounter_id == encounter_id)
                    .order_by(Prescription.created_at.desc())
                )
            ).all()
        )

    async def detail(self, prescription_id: UUID, hospital_id: UUID) -> dict:
        prescription = await self.get(prescription_id, hospital_id)
        items = list(
            (
                await self.session.scalars(
                    select(PrescriptionItem).where(PrescriptionItem.prescription_id == prescription_id)
                )
            ).all()
        )
        return {"prescription": prescription, "items": items}

    async def update_draft(
        self, prescription_id: UUID, payload: PrescriptionDraftUpdate, hospital_id: UUID
    ) -> Prescription:
        prescription = await self.get(prescription_id, hospital_id, for_update=True)
        if prescription.status != "draft":
            raise HTTPException(409, "only draft prescriptions can be edited")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(prescription, key, value)
        await self.session.commit()
        return prescription

    async def issue(self, prescription_id: UUID, payload: PrescriptionIssue, hospital_id: UUID) -> Prescription:
        prescription = await self.get(prescription_id, hospital_id, for_update=True)
        if prescription.status != "draft":
            raise HTTPException(409, "only draft prescriptions can be issued")
        prescription.status = "issued"
        prescription.issued_at = payload.issued_at
        prescription.signed_at = payload.signed_at
        await self.session.commit()
        return prescription

    async def cancel(self, prescription_id: UUID, payload: PrescriptionCancel, hospital_id: UUID) -> Prescription:
        prescription = await self.get(prescription_id, hospital_id, for_update=True)
        if prescription.status == "cancelled":
            raise HTTPException(409, "prescription is already cancelled")
        prescription.status = "cancelled"
        prescription.cancelled_at = payload.cancelled_at
        prescription.cancellation_reason = payload.reason
        await self.session.commit()
        return prescription
