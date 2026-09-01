from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.workforce import ClinicalStaffProfile, Staff, StaffWardAssignment
from src.db.repositories.staff import StaffRepository, StaffWardAssignmentRepository
from src.schemas.staff import StaffCreate, StaffUpdate, WardAssignmentCreate


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

    async def list(
        self,
        hospital_id: UUID,
        *,
        query: str | None,
        staff_type: str | None,
        ward_id: UUID | None,
        page: int,
        page_size: int,
    ) -> tuple[list[Staff], int]:
        statement = select(Staff).where(Staff.hospital_id == hospital_id)
        count_statement = select(func.count(func.distinct(Staff.id))).where(Staff.hospital_id == hospital_id)
        if ward_id:
            statement = statement.join(StaffWardAssignment, StaffWardAssignment.staff_id == Staff.id).where(
                StaffWardAssignment.ward_id == ward_id,
                StaffWardAssignment.assigned_until.is_(None),
            )
            count_statement = count_statement.join(StaffWardAssignment, StaffWardAssignment.staff_id == Staff.id).where(
                StaffWardAssignment.ward_id == ward_id, StaffWardAssignment.assigned_until.is_(None)
            )
        if staff_type:
            statement = statement.where(Staff.staff_type == staff_type)
            count_statement = count_statement.where(Staff.staff_type == staff_type)
        if query:
            pattern = f"%{query.strip()}%"
            condition = or_(
                Staff.first_name.ilike(pattern),
                Staff.last_name.ilike(pattern),
                Staff.employee_code.ilike(pattern),
                Staff.email.ilike(pattern),
            )
            statement = statement.where(condition)
            count_statement = count_statement.where(condition)
        statement = statement.distinct().order_by(Staff.first_name, Staff.last_name)
        items = list((await self.session.scalars(statement.limit(page_size).offset((page - 1) * page_size))).all())
        total = await self.session.scalar(count_statement) or 0
        return items, total

    async def update(self, staff_id: UUID, payload: StaffUpdate) -> Staff:
        member = await self.get(staff_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(member, key, value)
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def deactivate(self, staff_id: UUID) -> Staff:
        member = await self.get(staff_id)
        member.employment_status = "inactive"
        await self.session.commit()
        return member

    async def list_assignments(self, staff_id: UUID) -> list[StaffWardAssignment]:
        await self.get(staff_id)
        return list(
            (
                await self.session.scalars(
                    select(StaffWardAssignment)
                    .where(StaffWardAssignment.staff_id == staff_id)
                    .order_by(StaffWardAssignment.assigned_from.desc())
                )
            ).all()
        )

    async def end_assignment(self, assignment_id: UUID, ended_at) -> StaffWardAssignment:
        assignment = await self.assignments.get(assignment_id)
        if assignment is None:
            raise HTTPException(404, "ward assignment not found")
        assignment.assigned_until = ended_at
        await self.session.commit()
        return assignment

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
