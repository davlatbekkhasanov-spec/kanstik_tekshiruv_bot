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
            return
        except Exception as exc:
            last_err = exc
            log.warning("Migration try failed args=%s: %s", connect_args, exc)
    raise RuntimeError(f"Migration failed: {last_err}")
