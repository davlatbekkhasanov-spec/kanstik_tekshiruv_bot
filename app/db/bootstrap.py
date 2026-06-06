from __future__ import annotations

import logging
import os

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.db.session import configure_database
from app.db.url import (
    alembic_sync_url,
    async_connect_variants,
    database_url_candidates,
    db_host,
    sync_connect_args,
    sync_connect_variants,
    to_sync_env_url,
)

log = logging.getLogger(__name__)

_sync_url: str | None = None
_sync_connect_args: dict | None = None


def get_sync_url() -> str | None:
    return _sync_url


def get_sync_connect_args() -> dict | None:
    return _sync_connect_args


async def setup_database() -> tuple[str, dict]:
    """Ishlaydigan URL + connect_args topiladi."""
    global _sync_url, _sync_connect_args
    candidates = database_url_candidates()
    if not candidates:
        raise RuntimeError("DATABASE_URL topilmadi — Postgres ni bot servisiga ulang")

    last_err: Exception | None = None
    for url in candidates:
        for connect_args in async_connect_variants(url):
            try:
                probe = create_async_engine(
                    url,
                    pool_pre_ping=True,
                    connect_args=connect_args,
                )
                async with probe.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                await probe.dispose()
                configure_database(url, connect_args)
                os.environ["DATABASE_URL"] = to_sync_env_url(url)
                get_settings.cache_clear()
                log.info(
                    "Database OK host=%s ssl=%s",
                    db_host(url),
                    bool(connect_args.get("ssl")),
                )
                return url, connect_args
            except Exception as exc:
                last_err = exc
                log.warning(
                    "DB probe failed host=%s args=%s: %s",
                    db_host(url),
                    connect_args,
                    exc,
                )

    raise RuntimeError(f"Barcha DB urinishlari muvaffaqiyatsiz: {last_err}")


def ensure_inspection_schema(url: str) -> None:
    """Migration o'tmasa ham kerakli ustunlar va enum qo'shiladi."""
    from sqlalchemy import inspect

    sync = alembic_sync_url(url)
    connect_args = _sync_connect_args or sync_connect_args(url)
    engine = create_engine(sync, connect_args=connect_args)
    try:
        if not inspect(engine).has_table("inspections"):
            return
        cols = {c["name"] for c in inspect(engine).get_columns("inspections")}
        with engine.begin() as conn:
            if "return_chat_id" not in cols:
                conn.execute(
                    text("ALTER TABLE inspections ADD COLUMN return_chat_id BIGINT")
                )
                log.info("Added column inspections.return_chat_id")
            if "fix_submitted_at" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE inspections ADD COLUMN fix_submitted_at "
                        "TIMESTAMP WITH TIME ZONE"
                    )
                )
                log.info("Added column inspections.fix_submitted_at")
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(
                text(
                    "ALTER TYPE inspection_status ADD VALUE IF NOT EXISTS 'fix_submitted'"
                )
            )
    finally:
        engine.dispose()


def ensure_schema(url: str) -> None:
    """Jadvallar yo'q bo'lsa yaratadi (alembic muvaffaqiyatsiz bo'lsa)."""
    from sqlalchemy import inspect

    from app.db.base import Base

    sync = alembic_sync_url(url)
    connect_args = _sync_connect_args or sync_connect_args(url)
    engine = create_engine(sync, connect_args=connect_args)
    try:
        if not inspect(engine).has_table("users"):
            log.warning("users jadvali yo'q — create_all")
            Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def run_migrations(url: str) -> None:
    from alembic import command
    from alembic.config import Config

    global _sync_url, _sync_connect_args
    sync = alembic_sync_url(url)
    last_err: Exception | None = None
    for connect_args in sync_connect_variants(url):
        try:
            probe = create_engine(sync, connect_args=connect_args)
            with probe.connect() as conn:
                conn.execute(text("SELECT 1"))
            probe.dispose()
            _sync_url = sync
            _sync_connect_args = connect_args
            cfg = Config("alembic.ini")
            command.upgrade(cfg, "head")
            log.info("Alembic upgrade head OK")
            ensure_inspection_schema(url)
            return
        except Exception as exc:
            last_err = exc
            log.warning("Migration try failed args=%s: %s", connect_args, exc)
    log.error("Alembic failed, trying schema repair: %s", last_err)
    ensure_inspection_schema(url)
    ensure_schema(url)
