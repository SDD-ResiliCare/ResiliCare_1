"""Per-doctor current-patient and waiting-workload orchestration."""

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import DoctorWorkItem, Encounter
from src.db.models.organization import Ward
from src.db.models.patient import Patient
from src.db.models.workforce import Staff, StaffWardAssignment


class DoctorWorkService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_workloads(self, hospital_id: UUID, ward_id: UUID | None = None) -> list[dict]:
        statement = select(Staff).where(
            Staff.hospital_id == hospital_id,
            Staff.staff_type == "doctor",
            Staff.employment_status == "active",
        )
        if ward_id is not None:
            statement = statement.join(StaffWardAssignment, StaffWardAssignment.staff_id == Staff.id).where(
                StaffWardAssignment.ward_id == ward_id,
                StaffWardAssignment.assigned_until.is_(None),
            )
        doctors = list((await self.session.scalars(statement.distinct().order_by(Staff.first_name))).all())
        workloads = [await self._workload(doctor) for doctor in doctors]
        workloads.sort(key=lambda w: (w["waiting_count"], w["doctor"]["first_name"]), reverse=True)
        return workloads

    async def get_workload(self, doctor_id: UUID, hospital_id: UUID) -> dict:
        doctor = await self.session.scalar(
            select(Staff).where(
                Staff.id == doctor_id,
                Staff.hospital_id == hospital_id,
                Staff.staff_type == "doctor",
                Staff.employment_status == "active",
            )
        )
        if doctor is None:
            raise HTTPException(404, "active doctor not found in hospital")
        return await self._workload(doctor)

    async def _workload(self, doctor: Staff) -> dict:
        rows = (
            await self.session.execute(
                select(DoctorWorkItem, Encounter, Patient, Ward)
                .join(Encounter, Encounter.id == DoctorWorkItem.encounter_id)
                .join(Patient, Patient.id == Encounter.patient_id)
                .join(Ward, Ward.id == DoctorWorkItem.ward_id)
                .where(
                    DoctorWorkItem.doctor_staff_id == doctor.id,
                    DoctorWorkItem.status.in_(("waiting", "in_service")),
                )
                .order_by(
                    case((DoctorWorkItem.status == "in_service", 0), else_=1),
                    DoctorWorkItem.priority_esi,
                    DoctorWorkItem.queued_at,
                )
            )
        ).all()
        current = None
        waiting = []
        for work_item, encounter, patient, ward in rows:
            summary = self._patient_summary(work_item, encounter, patient, ward, None)
            if work_item.status == "in_service":
                current = summary
            else:
                summary["queue_position"] = len(waiting) + 1
                waiting.append(summary)
        return {
            "doctor": self._doctor_summary(doctor),
            "availability": "busy" if current else "free",
            "current_patient": current,
            "waiting_count": len(waiting),
            "waiting_patients": waiting,
        }

    async def finish_encounter_work(
        self, encounter_id: UUID, completed_at: datetime, reason: str
    ) -> tuple[DoctorWorkItem | None, DoctorWorkItem | None]:
        """Finish active doctor work and promote that doctor's next queued patient."""
        work_item = await self.session.scalar(
            select(DoctorWorkItem)
            .where(
                DoctorWorkItem.encounter_id == encounter_id,
                DoctorWorkItem.status.in_(("waiting", "in_service")),
            )
            .with_for_update()
        )
        if work_item is None:
            return None, None
        if completed_at < work_item.queued_at or (
            work_item.started_at is not None and completed_at < work_item.started_at
        ):
            raise HTTPException(422, "doctor work completion cannot predate its queue or start time")
        was_in_service = work_item.status == "in_service"
        if was_in_service:
            work_item.status = "completed"
            work_item.completed_at = completed_at
        else:
            work_item.status = "cancelled"
        work_item.end_reason = reason
        if not was_in_service:
            return work_item, None

        next_item = await self.promote_next(work_item.doctor_staff_id, completed_at)
        return work_item, next_item

    async def promote_next(self, doctor_id: UUID, started_at: datetime) -> DoctorWorkItem | None:
        """Promote the highest-acuity waiting item after serializing on the doctor row."""
        await self.session.scalar(select(Staff).where(Staff.id == doctor_id).with_for_update())
        next_item = await self.session.scalar(
            select(DoctorWorkItem)
            .where(
                DoctorWorkItem.doctor_staff_id == doctor_id,
                DoctorWorkItem.status == "waiting",
            )
            .order_by(DoctorWorkItem.priority_esi, DoctorWorkItem.queued_at)
            .with_for_update()
            .limit(1)
        )
        if next_item is not None:
            effective_start = max(started_at, next_item.queued_at)
            next_item.status = "in_service"
            next_item.started_at = effective_start
            next_encounter = await self.session.get(Encounter, next_item.encounter_id, with_for_update=True)
            if next_encounter is not None:
                next_encounter.status = "in_care"
                next_encounter.care_started_at = effective_start
        return next_item

    @staticmethod
    def _patient_summary(
        work_item: DoctorWorkItem,
        encounter: Encounter,
        patient: Patient,
        ward: Ward,
        queue_position: int | None,
    ) -> dict:
        return {
            "work_item_id": work_item.id,
            "encounter_id": encounter.id,
            "encounter_code": encounter.encounter_code,
            "patient_id": patient.id,
            "patient_name": " ".join(part for part in (patient.first_name, patient.last_name) if part),
            "ward": {"id": ward.id, "ward_code": ward.ward_code, "name": ward.name, "ward_type": ward.ward_type},
            "status": work_item.status,
            "confirmed_esi": work_item.priority_esi,
            "queue_position": queue_position,
            "queued_at": work_item.queued_at,
            "started_at": work_item.started_at,
            "allocation_overview": work_item.allocation_overview,
            "allocation_overview_factors": work_item.allocation_overview_factors,
        }

    @staticmethod
    def _doctor_summary(doctor: Staff) -> dict:
        return {
            "id": doctor.id,
            "employee_code": doctor.employee_code,
            "first_name": doctor.first_name,
            "last_name": doctor.last_name,
        }
