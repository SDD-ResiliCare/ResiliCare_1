"""Compose the authenticated frontend bootstrap context."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Queue
from src.db.models.organization import Hospital, HospitalOperationalConfig, Ward
from src.db.models.workforce import ClinicalStaffProfile, Staff, StaffWardAssignment

ROLE_PERMISSIONS = {
    "platform_admin": ["manage_platform", "manage_hospitals", "view_audit"],
    "administrator": ["manage_hospital", "manage_staff", "manage_billing", "view_audit"],
    "doctor": ["view_patients", "manage_encounters", "confirm_triage", "manage_prescriptions"],
    "nurse": ["view_patients", "manage_queue", "record_vitals", "perform_triage"],
    "billing_staff": ["view_patients", "manage_billing"],
    "receptionist": ["register_patients", "manage_queue", "allocate_care_team"],
    "reception_staff": ["register_patients", "manage_queue", "allocate_care_team"],
    "patient": ["view_own_health"],
}


class AppContextService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(
        self,
        *,
        auth_user_id: UUID,
        platform_role: str | None,
        staff_id: UUID | None,
        hospital_id: UUID | None,
        staff_type: str | None,
        patient_ids: tuple[UUID, ...],
    ) -> dict:
        staff = await self.session.get(Staff, staff_id) if staff_id else None
        clinical_profile = await self.session.get(ClinicalStaffProfile, staff_id) if staff_id else None
        hospital = await self.session.get(Hospital, hospital_id) if hospital_id else None
        assignments = []
        wards = []
        queue = None
        operational_config = None
        if staff_id:
            assignments = list(
                (
                    await self.session.scalars(
                        select(StaffWardAssignment).where(
                            StaffWardAssignment.staff_id == staff_id,
                            StaffWardAssignment.assigned_until.is_(None),
                        )
                    )
                ).all()
            )
            ward_ids = [assignment.ward_id for assignment in assignments]
            if ward_ids:
                wards = list((await self.session.scalars(select(Ward).where(Ward.id.in_(ward_ids)))).all())
        if hospital_id:
            queue = await self.session.scalar(
                select(Queue).where(Queue.hospital_id == hospital_id, Queue.status == "active")
            )
            operational_config = await self.session.scalar(
                select(HospitalOperationalConfig).where(
                    HospitalOperationalConfig.hospital_id == hospital_id,
                    HospitalOperationalConfig.is_active.is_(True),
                )
            )
        role = platform_role or staff_type or ("patient" if patient_ids else None)
        return {
            "identity": {
                "auth_user_id": auth_user_id,
                "role": role,
                "permissions": ROLE_PERMISSIONS.get(role or "", []),
                "patient_ids": patient_ids,
            },
            "staff": staff,
            "clinical_profile": clinical_profile,
            "hospital": hospital,
            "ward_assignments": assignments,
            "wards": wards,
            "active_queue": queue,
            "operational_config": operational_config,
        }
