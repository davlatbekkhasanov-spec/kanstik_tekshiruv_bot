from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

from app.config import Settings

log = logging.getLogger(__name__)


def uses_private_notify(settings: Settings) -> bool:
    """Guruh sozlanmaguncha — barcha tekshiruv xabarlari admin lichkasiga."""
    return settings.setup_mode


def uses_group_workflow(settings: Settings) -> bool:
    """Teruvchi lichka → guruh; tekshiruvchi lichkada davom etadi."""
    return not uses_private_notify(settings) and bool(settings.review_group_id)


def error_group_chats(settings: Settings) -> list[int]:
    if uses_private_notify(settings):
        return sorted(settings.admin_id_set())
    if settings.return_group_id:
        return [settings.return_group_id]
    if settings.review_group_id:
        return [settings.review_group_id]
    return sorted(settings.admin_id_set())


def confirm_group_chats(settings: Settings) -> list[int]:
    if uses_private_notify(settings):
        return sorted(settings.admin_id_set())
    if settings.review_group_id:
        return [settings.review_group_id]
    return sorted(settings.admin_id_set())


def review_target_chats(settings: Settings) -> list[int]:
    if uses_private_notify(settings):
        return sorted(settings.admin_id_set())
    if settings.review_group_id:
        return [settings.review_group_id]
    return sorted(settings.admin_id_set())


def return_target_chats(settings: Settings) -> list[int]:
    if uses_private_notify(settings):
        return sorted(settings.admin_id_set())
    if settings.return_group_id:
        return [settings.return_group_id]
    return sorted(settings.admin_id_set())


def unique_chat_ids(chats: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for cid in chats:
        if cid and cid not in seen:
            seen.add(cid)
            out.append(cid)
    return out


async def send_photo_notice(
    bot: Bot,
    *,
    chat_ids: list[int],
    photo_file_id: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> tuple[int, int] | None:
    """Birinchi muvaffaqiyatli yuborilgan (chat_id, message_id)."""
    if not chat_ids:
        log.error("Notify chat_ids bo'sh — ADMIN_IDS yoki guruh ID ni tekshiring")
        return None
    prefix = ""
    if len(chat_ids) > 1:
        prefix = "🧪 <i>Test (lichka)</i>\n\n"
    first: tuple[int, int] | None = None
    cap = (prefix + caption)[:1024]
    for cid in chat_ids:
        try:
            msg = await bot.send_photo(
                cid,
                photo_file_id,
                caption=cap,
                reply_markup=reply_markup,
                parse_mode="HTML",
            )
            if first is None:
                first = (cid, msg.message_id)
        except Exception:
            log.exception("send_photo chat_id=%s", cid)
    return first


async def edit_photo_caption(
    bot: Bot,
    *,
    chat_id: int,
    message_id: int | None,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> bool:
    if not message_id:
        return False
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption[:1024],
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return True
    except Exception:
        log.exception("edit caption chat=%s msg=%s", chat_id, message_id)
        return False


async def send_text_notice(
    bot: Bot,
    *,
    chat_ids: list[int],
    text: str,
) -> None:
    for cid in chat_ids:
        try:
            await bot.send_message(cid, text[:4096], parse_mode="HTML")
        except Exception:
            log.exception("send_message chat_id=%s", cid)


async def send_voice_notice(
    bot: Bot,
    *,
    chat_ids: list[int],
    voice_file_id: str,
    caption: str | None = None,
) -> None:
    for cid in chat_ids:
        try:
            await bot.send_voice(cid, voice_file_id, caption=caption)
        except Exception:
            log.exception("send_voice chat_id=%s", cid)
