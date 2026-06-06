from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from sqlalchemy import select

from app.bot.keyboards import start_review_kb
from app.config import get_settings
from app.constants import InspectionStatus
from app.db.models import Inspection
from app.db.session import SessionLocal
from app.services import inspection as svc
from app.services import notify as ntf

log = logging.getLogger(__name__)


async def run_pending_refresh(bot: Bot) -> None:
    """Kutilayotgan kartalarda vaqt avtomatik yangilanadi."""
    interval = get_settings().pending_refresh_seconds
    while True:
        await asyncio.sleep(interval)
        if SessionLocal is None:
            continue
        try:
            async with SessionLocal() as session:
                rows = (
                    await session.scalars(
                        select(Inspection).where(
                            Inspection.status == InspectionStatus.pending,
                            Inspection.review_chat_id.isnot(None),
                            Inspection.review_group_message_id.isnot(None),
                        )
                    )
                ).all()
                for insp in rows:
                    cap = svc.pending_inspection_text(insp)
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.review_chat_id),
                        message_id=int(insp.review_group_message_id),
                        caption=cap,
                        reply_markup=start_review_kb(insp.id, insp.invoice_number),
                    )
        except Exception:
            log.exception("pending_refresh tick failed")
