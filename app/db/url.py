from __future__ import annotations

import os
import ssl
from urllib.parse import quote_plus, urlparse


def normalize_database_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if u.startswith("postgres://"):
        u = "postgresql+asyncpg://" + u[len("postgres://") :]
    elif u.startswith("postgresql://") and "+asyncpg" not in u and "+psycopg2" not in u:
        u = "postgresql+asyncpg://" + u[len("postgresql://") :]
    return u


def build_from_pg_env() -> str:
    host = os.getenv("PGHOST", "").strip()
    if not host:
        return ""
    port = (os.getenv("PGPORT", "5432") or "5432").strip()
    user = (os.getenv("PGUSER", "postgres") or "postgres").strip()
    password = os.getenv("PGPASSWORD", "")
    db = (os.getenv("PGDATABASE", "railway") or "railway").strip()
    return normalize_database_url(
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{db}"
    )


def resolve_database_url() -> str:
    candidates = database_url_candidates()
    return candidates[0] if candidates else ""


def database_url_candidates() -> list[str]:
    urls: list[str] = []
    for key in (
        "DATABASE_URL",
        "DATABASE_PRIVATE_URL",
        "DATABASE_PUBLIC_URL",
        "POSTGRES_URL",
    ):
        val = os.getenv(key, "").strip()
        if val:
            urls.append(normalize_database_url(val))
    built = build_from_pg_env()
    if built:
        urls.append(built)
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def db_host(url: str) -> str:
    try:
        return urlparse(url.replace("+asyncpg", "")).hostname or "?"
    except Exception:
        return "?"


def is_local_db(url: str) -> bool:
    low = (url or "").lower()
    return any(x in low for x in ("localhost", "127.0.0.1", "@host:5432"))


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def async_connect_variants(url: str) -> list[dict]:
    """Railway: avval ichki tarmoq (SSLsiz), keyin SSL."""
    if is_local_db(url):
        return [{}]
    if "railway.internal" in url:
        return [{}, {"ssl": True}, {"ssl": _ssl_context()}]
    return [{"ssl": _ssl_context()}, {"ssl": True}, {}]


def async_connect_args(url: str) -> dict:
    variants = async_connect_variants(url)
    return variants[0] if variants else {}


def sync_connect_variants(url: str) -> list[dict]:
    if is_local_db(url):
        return [{}]
    if "railway.internal" in url:
        return [{}, {"sslmode": "prefer"}, {"sslmode": "require"}]
    return [{"sslmode": "require"}, {"sslmode": "prefer"}, {}]


def sync_connect_args(url: str) -> dict:
    variants = sync_connect_variants(url)
    return variants[0] if variants else {}


def alembic_sync_url(async_url: str) -> str:
    u = normalize_database_url(async_url).replace("+asyncpg", "")
    if u.startswith("postgresql://"):
        return "postgresql+psycopg2://" + u[len("postgresql://") :]
    return u


def to_sync_env_url(async_url: str) -> str:
    u = normalize_database_url(async_url)
    return u.replace("postgresql+asyncpg://", "postgresql://")
