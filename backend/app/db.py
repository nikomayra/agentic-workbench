from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


async def get_async_db_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency that yields an async SQLAlchemy session."""
    async with AsyncSessionLocal() as async_session:
        yield async_session


@asynccontextmanager
async def get_async_db_ctx() -> AsyncGenerator[AsyncSession]:
    """Yield a session to code running outside FastAPI's dependency system."""
    async with AsyncSessionLocal() as session:
        yield session
