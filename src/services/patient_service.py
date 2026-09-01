from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Encounter
from src.db.models.patient import Patient, PatientAccessLink, PatientAllergy, PatientCondition, PatientIdentifier
from src.db.models.triage import TriageAssessment, VitalObservation
from src.db.repositories.patients import PatientIdentifierRepository, PatientRepository
from src.schemas.patient import (
    PatientAccessLinkCreate,
    PatientAllergyCreate,
    PatientConditionCreate,
    PatientCreate,
    PatientIdentifierCreate,
    PatientUpdate,
)


class PatientService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.patients = PatientRepository(session)
        self.identifiers = PatientIdentifierRepository(session)

    async def create(self, payload: PatientCreate, hospital_id: UUID) -> Patient:
        patient = await self.patients.add(Patient(**payload.model_dump(), status="active"))
        await self.identifiers.add(
            PatientIdentifier(
                patient_id=patient.id,
                hospital_id=hospital_id,
                identifier_type="mrn",
                identifier_value=f"RC-{patient.id.hex[:12].upper()}",
                valid_from=datetime.now(UTC).date(),
            )
        )
        await self.session.commit()
        return patient

    async def get(self, patient_id: UUID) -> Patient:
        patient = await self.patients.get(patient_id)
        if patient is None:
            raise HTTPException(404, "patient not found")
        return patient

    async def get_for_hospital(self, patient_id: UUID, hospital_id: UUID | None) -> Patient:
        if hospital_id is None:
            return await self.get(patient_id)
        patient = await self.session.scalar(
            select(Patient)
            .outerjoin(PatientIdentifier, PatientIdentifier.patient_id == Patient.id)
            .outerjoin(Encounter, Encounter.patient_id == Patient.id)
            .where(Patient.id == patient_id)
            .where(or_(PatientIdentifier.hospital_id == hospital_id, Encounter.hospital_id == hospital_id))
        )
        if patient is None:
            raise HTTPException(404, "patient not found")
        return patient

    async def list_for_hospital(
        self, hospital_id: UUID, *, query: str | None, page: int, page_size: int
    ) -> tuple[list[Patient], int]:
        access = or_(PatientIdentifier.hospital_id == hospital_id, Encounter.hospital_id == hospital_id)
        statement = (
            select(Patient)
            .outerjoin(PatientIdentifier, PatientIdentifier.patient_id == Patient.id)
            .outerjoin(Encounter, Encounter.patient_id == Patient.id)
            .where(access)
        )
        count_statement = (
            select(func.count(func.distinct(Patient.id)))
            .outerjoin(PatientIdentifier, PatientIdentifier.patient_id == Patient.id)
            .outerjoin(Encounter, Encounter.patient_id == Patient.id)
            .where(access)
        )
        if query:
            pattern = f"%{query.strip()}%"
            search = or_(
                Patient.first_name.ilike(pattern),
                Patient.last_name.ilike(pattern),
                Patient.phone.ilike(pattern),
                Patient.email.ilike(pattern),
                PatientIdentifier.identifier_value.ilike(pattern),
            )
            statement = statement.where(search)
            count_statement = count_statement.where(search)
        statement = statement.distinct().order_by(Patient.first_name, Patient.last_name)
        items = list((await self.session.scalars(statement.limit(page_size).offset((page - 1) * page_size))).all())
        total = await self.session.scalar(count_statement) or 0
        return items, total

    async def update(self, patient_id: UUID, payload: PatientUpdate) -> Patient:
        patient = await self.get(patient_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(patient, key, value)
        await self.session.commit()
        await self.session.refresh(patient)
        return patient

    async def archive(self, patient_id: UUID) -> Patient:
        patient = await self.get(patient_id)
        patient.status = "inactive"
        await self.session.commit()
        return patient

    async def list_allergies(self, patient_id: UUID) -> list[PatientAllergy]:
        await self.get(patient_id)
        return list(
            (await self.session.scalars(select(PatientAllergy).where(PatientAllergy.patient_id == patient_id))).all()
        )

    async def list_conditions(self, patient_id: UUID) -> list[PatientCondition]:
        await self.get(patient_id)
        return list(
            (
                await self.session.scalars(select(PatientCondition).where(PatientCondition.patient_id == patient_id))
            ).all()
        )

    async def add_identifier(self, patient_id: UUID, payload: PatientIdentifierCreate) -> PatientIdentifier:
        await self.get(patient_id)
        identifier = await self.identifiers.add(PatientIdentifier(patient_id=patient_id, **payload.model_dump()))
        await self.session.commit()
        return identifier

    async def add_allergy(self, patient_id: UUID, payload: PatientAllergyCreate, staff_id: UUID) -> PatientAllergy:
        await self.get(patient_id)
        allergy = PatientAllergy(patient_id=patient_id, recorded_by_staff_id=staff_id, **payload.model_dump())
        self.session.add(allergy)
        await self.session.commit()
        await self.session.refresh(allergy)
        return allergy

    async def add_condition(
        self, patient_id: UUID, payload: PatientConditionCreate, staff_id: UUID
    ) -> PatientCondition:
        await self.get(patient_id)
        condition = PatientCondition(patient_id=patient_id, recorded_by_staff_id=staff_id, **payload.model_dump())
        self.session.add(condition)
        await self.session.commit()
        await self.session.refresh(condition)
        return condition

    async def grant_portal_access(self, patient_id: UUID, payload: PatientAccessLinkCreate) -> PatientAccessLink:
        await self.get(patient_id)
        link = PatientAccessLink(patient_id=patient_id, status="active", **payload.model_dump())
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def portal_summary(self, patient_id: UUID) -> dict:
        patient = await self.get(patient_id)
        encounters = list(
            (
                await self.session.scalars(
                    select(Encounter).where(Encounter.patient_id == patient_id).order_by(Encounter.arrived_at.desc())
                )
            ).all()
        )
        conditions = list(
            (
                await self.session.scalars(select(PatientCondition).where(PatientCondition.patient_id == patient_id))
            ).all()
        )
        allergies = list(
            (await self.session.scalars(select(PatientAllergy).where(PatientAllergy.patient_id == patient_id))).all()
        )
        visits = []
        for encounter in encounters:
            latest_vitals = await self.session.scalar(
                select(VitalObservation)
                .where(VitalObservation.encounter_id == encounter.id)
                .order_by(VitalObservation.observed_at.desc())
                .limit(1)
            )
            latest_assessment = await self.session.scalar(
                select(TriageAssessment)
                .where(TriageAssessment.encounter_id == encounter.id)
                .order_by(TriageAssessment.assessment_number.desc())
                .limit(1)
            )
            visits.append(
                {
                    "encounter_id": encounter.id,
                    "encounter_code": encounter.encounter_code,
                    "status": encounter.status,
                    "arrived_at": encounter.arrived_at,
                    "completed_at": encounter.completed_at,
                    "latest_vitals": latest_vitals,
                    "latest_triage_assessment": latest_assessment,
                }
            )
        return {"patient": patient, "conditions": conditions, "allergies": allergies, "encounters": visits}
