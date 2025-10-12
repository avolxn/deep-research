from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from deep_research.backend.models import Base
from deep_research.config import settings

engine = create_async_engine(settings.DATABASE.URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Инициализация базы данных - создание всех таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД

    Returns:
        AsyncGenerator[AsyncSession, None]: Сессия базы данных

    Yields:
        Iterator[AsyncGenerator[AsyncSession, None]]: Сессия базы данных
    """
    async with async_session_maker() as session:
        yield session
