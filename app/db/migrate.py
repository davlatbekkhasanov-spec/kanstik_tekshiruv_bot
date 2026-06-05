from __future__ import annotations

import logging
import os
from urllib.parse import quote_plus

from alembic import command
from alembic.config import Config

log = logging.getLogger(__name__)


def upgrade_head() -> None:
    cfg = Config("alembic.ini")
    command.upgrade(cfg, "head")
    log.info("Alembic upgrade head OK")
