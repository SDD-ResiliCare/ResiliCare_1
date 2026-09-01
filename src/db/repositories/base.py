"""Small reusable repository primitive; transaction ownership stays in services."""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base


class Repository[ModelT: Base]:
    def __init__(self, session: AsyncSession, model: type[ModelT]):
        self.session = session
        self.model = model

    async def get(self, resource_id: UUID, *, for_update: bool = False) -> ModelT | None:
        statement = select(self.model).where(self.model.id == resource_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list(self, statement: Select | None = None, *, limit: int = 100, offset: int = 0) -> list[ModelT]:
        query = (statement or select(self.model)).limit(limit).offset(offset)
        return list((await self.session.scalars(query)).all())

    async def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
