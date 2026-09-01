from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.workforce import ClinicalStaffProfile, Staff, StaffWardAssignment
from src.db.repositories.staff import StaffRepository, StaffWardAssignmentRepository
from src.schemas.staff import StaffCreate, WardAssignmentCreate


class StaffService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.staff = StaffRepository(session)
        self.assignments = StaffWardAssignmentRepository(session)

    async def create(self, payload: StaffCreate) -> Staff:
        values = payload.model_dump()
        profile_values = {
            key: values.pop(key)
            for key in (
                "registration_number",
                "registration_authority",
                "qualification",
                "specialty",
                "practice_started_on",
                "professional_grade",
                "bio",
            )
        }
        member = await self.staff.add(Staff(**values, employment_status="active"))
        if member.staff_type in {"doctor", "nurse"}:
            self.session.add(ClinicalStaffProfile(staff_id=member.id, **profile_values))
        await self.session.commit()
        return member

    async def get(self, staff_id: UUID) -> Staff:
        member = await self.staff.get(staff_id)
        if member is None:
            raise HTTPException(404, "staff member not found")
        return member

    async def assign_ward(
        self, staff_id: UUID, payload: WardAssignmentCreate, assigned_by: UUID | None
    ) -> StaffWardAssignment:
        await self.get(staff_id)
        assignment = await self.assignments.add(
            StaffWardAssignment(
                staff_id=staff_id,
                assigned_by_staff_id=assigned_by,
                **payload.model_dump(),
            )
        )
        await self.session.commit()
        return assignment
