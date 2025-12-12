from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from deep_research.config import config
from deep_research.models import Base

engine = create_async_engine(config.URL)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    """Инициализация базы данных - создание всех таблиц."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency для получения сессии БД."""
    async with async_session_maker() as session:
        yield session


async def close_db() -> None:
    """Закрытие соединения с базой данных."""
    await engine.dispose()
