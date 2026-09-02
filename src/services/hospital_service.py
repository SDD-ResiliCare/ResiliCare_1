import hashlib
import json
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.encounter import Queue
from src.db.models.organization import EscalationRoute, EsiCareAreaRule, Hospital, HospitalOperationalConfig, Ward
from src.db.repositories.hospitals import HospitalRepository, WardRepository
from src.schemas.hospital import HospitalCreate, HospitalUpdate, OperationalConfigCreate, WardCreate, WardUpdate


class HospitalService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.hospitals = HospitalRepository(session)
        self.wards = WardRepository(session)

    async def create_hospital(self, payload: HospitalCreate) -> Hospital:
        hospital = await self.hospitals.add(Hospital(**payload.model_dump(), status="active"))
        self.session.add(
            Queue(
                hospital_id=hospital.id,
                queue_code="MAIN_PATIENT_QUEUE",
                name="Main Patient Queue",
                queue_type="patient",
                status="active",
            )
        )
        await self.session.commit()
        return hospital

    async def list_hospitals(self, *, page: int, page_size: int) -> tuple[list[Hospital], int]:
        statement = select(Hospital).order_by(Hospital.name)
        items = await self.hospitals.list(statement, limit=page_size, offset=(page - 1) * page_size)
        total = await self.session.scalar(select(func.count()).select_from(Hospital)) or 0
        return items, total

    async def get_hospital(self, hospital_id: UUID) -> Hospital:
        hospital = await self.hospitals.get(hospital_id)
        if hospital is None:
            raise HTTPException(404, "hospital not found")
        return hospital

    async def update_hospital(self, hospital_id: UUID, payload: HospitalUpdate) -> Hospital:
        hospital = await self.get_hospital(hospital_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(hospital, key, value)
        await self.session.commit()
        await self.session.refresh(hospital)
        return hospital

    async def deactivate_hospital(self, hospital_id: UUID) -> Hospital:
        hospital = await self.get_hospital(hospital_id)
        hospital.status = "inactive"
        await self.session.execute(update(Queue).where(Queue.hospital_id == hospital_id).values(status="inactive"))
        await self.session.commit()
        return hospital

    async def create_ward(self, payload: WardCreate) -> Ward:
        await self.get_hospital(payload.hospital_id)
        ward = await self.wards.add(Ward(**payload.model_dump(), status="active"))
        await self.session.commit()
        return ward

    async def list_wards(self, hospital_id: UUID, *, include_inactive: bool = False) -> list[Ward]:
        await self.get_hospital(hospital_id)
        statement = select(Ward).where(Ward.hospital_id == hospital_id)
        if not include_inactive:
            statement = statement.where(Ward.status == "active")
        return list((await self.session.scalars(statement.order_by(Ward.name))).all())

    async def get_ward(self, ward_id: UUID) -> Ward:
        ward = await self.wards.get(ward_id)
        if ward is None:
            raise HTTPException(404, "ward not found")
        return ward

    async def update_ward(self, ward_id: UUID, payload: WardUpdate) -> Ward:
        ward = await self.get_ward(ward_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(ward, key, value)
        await self.session.commit()
        await self.session.refresh(ward)
        return ward

    async def deactivate_ward(self, ward_id: UUID) -> Ward:
        ward = await self.get_ward(ward_id)
        ward.status = "inactive"
        await self.session.commit()
        return ward

    async def list_operational_configs(self, hospital_id: UUID) -> list[HospitalOperationalConfig]:
        await self.get_hospital(hospital_id)
        return list(
            (
                await self.session.scalars(
                    select(HospitalOperationalConfig)
                    .where(HospitalOperationalConfig.hospital_id == hospital_id)
                    .order_by(HospitalOperationalConfig.version.desc())
                )
            ).all()
        )

    async def create_operational_config(
        self, hospital_id: UUID, payload: OperationalConfigCreate, staff_id: UUID | None
    ) -> HospitalOperationalConfig:
        await self.get_hospital(hospital_id)
        await self.session.execute(
            update(HospitalOperationalConfig)
            .where(HospitalOperationalConfig.hospital_id == hospital_id, HospitalOperationalConfig.is_active.is_(True))
            .values(is_active=False, effective_until=payload.effective_from)
        )
        snapshot = payload.model_dump(mode="json")
        config = HospitalOperationalConfig(
            hospital_id=hospital_id,
            version=payload.version,
            queue_warning_threshold=payload.queue_warning_threshold,
            surge_threshold=payload.surge_threshold,
            transfer_first_for_unsupported=payload.transfer_first_for_unsupported,
            effective_from=payload.effective_from,
            effective_until=payload.effective_until,
            created_by_staff_id=staff_id,
            is_active=True,
            config_hash=hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest(),
        )
        self.session.add(config)
        await self.session.flush()
        self.session.add_all(
            [EsiCareAreaRule(operational_config_id=config.id, **rule.model_dump()) for rule in payload.care_area_rules]
        )
        self.session.add_all(
            [
                EscalationRoute(operational_config_id=config.id, is_active=True, **route.model_dump())
                for route in payload.escalation_routes
            ]
        )
        await self.session.commit()
        await self.session.refresh(config)
        return config
