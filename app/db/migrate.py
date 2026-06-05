from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config

from app.db.url import alembic_sync_url, sync_connect_args

log = logging.getLogger(__name__)


def upgrade_head(database_url: str | None = None) -> None:
    cfg = Config("alembic.ini")
    if database_url:
        cfg.set_main_option("sqlalchemy.url", alembic_sync_url(database_url))
    command.upgrade(cfg, "head")
    log.info("Alembic upgrade head OK")
