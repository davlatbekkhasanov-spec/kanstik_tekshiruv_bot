from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = logging.getLogger(__name__)

engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None


def configure_database(url: str, connect_args: dict) -> None:
    global engine, SessionLocal
    if engine is not None:
        log.info("Reconfiguring database engine host=%s", url.split("@")[-1][:40])
    engine = create_async_engine(url, pool_pre_ping=True, connect_args=connect_args)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def require_session_local() -> async_sessionmaker[AsyncSession]:
    if SessionLocal is None:
        raise RuntimeError("Database not configured")
    return SessionLocal


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = require_session_local()
    async with factory() as session:
        yield session
