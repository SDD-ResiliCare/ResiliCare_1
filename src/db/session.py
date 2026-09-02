"""Async database engine and request-scoped sessions."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.settings import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)
AsyncSessionFactory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
