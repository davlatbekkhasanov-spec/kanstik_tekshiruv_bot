from __future__ import annotations

import ssl


def normalize_database_url(url: str) -> str:
    """Railway postgres:// → async SQLAlchemy uchun postgresql+asyncpg://"""
    u = (url or "").strip()
    if u.startswith("postgres://"):
        u = "postgresql+asyncpg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://") and "+asyncpg" not in u and "+psycopg2" not in u:
        u = "postgresql+asyncpg://" + u[len("postgresql://") :]
    return u


def is_local_db(url: str) -> bool:
    low = (url or "").lower()
    return any(x in low for x in ("localhost", "127.0.0.1", "@host:5432"))


def async_connect_args(url: str) -> dict:
    """Railway Postgres SSL (asyncpg)."""
    if is_local_db(url):
        return {}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return {"ssl": ctx}


def sync_connect_args(url: str) -> dict:
    """Alembic / psycopg2 uchun SSL."""
    if is_local_db(url):
        return {}
    return {"sslmode": "require"}


def alembic_sync_url(async_url: str) -> str:
    u = normalize_database_url(async_url).replace("+asyncpg", "")
    if u.startswith("postgresql://"):
        return "postgresql+psycopg2://" + u[len("postgresql://") :]
    return u
