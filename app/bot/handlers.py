from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from app.bot.keyboards import (
    error_types_kb,
    picker_fix_kb,
    picker_menu_kb,
    review_actions_kb,
    reviewer_confirm_fix_kb,
    start_review_kb,
)
from app.bot.states import PickerStates, ReviewerStates
from app.config import get_settings
from app.constants import ErrorType, UserRole
from app.db.session import SessionLocal, require_session_local
from app.employee_registry import is_team_member, operator_display_name
from app.services import inspection as svc
from app.services import notify as ntf

log = logging.getLogger(__name__)
router = Router()


def _settings():
    return get_settings()


def _is_admin(uid: int) -> bool:
    return uid in _settings().admin_id_set()


def _staff_denied(uid: int) -> str:
    return (
        "⛔ Bu bot faqat Kanstik jamoasi uchun.\n"
        f"Sizning ID: <code>{uid}</code>"
    )


def _msg_key(chat_id: int | None, message_id: int | None) -> tuple[int, int] | None:
    if chat_id and message_id:
        return (int(chat_id), int(message_id))
    return None


async def _can_confirm_fix(session, insp, uid: int, admin_ids: set[int]) -> bool:
    reviewer_tg = await svc.reviewer_telegram_id(session, insp)
    if uid in admin_ids:
        return True
    return bool(reviewer_tg and reviewer_tg == uid)


async def _apply_group_edits(
    bot: Bot,
    edits: list[tuple[tuple[int, int] | None, str, InlineKeyboardMarkup | None]],
) -> None:
    """Har bir (chat_id, message_id) faqat bir marta tahrirlanadi."""
    seen: set[tuple[int, int]] = set()
    for key, caption, reply_markup in edits:
        if not key or key in seen:
            continue
        seen.add(key)
        await ntf.edit_photo_caption(
            bot,
            chat_id=key[0],
            message_id=key[1],
            caption=caption,
            reply_markup=reply_markup,
        )


@router.message(Command("botconfig"))
async def cmd_botconfig(message: Message, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        return
    st = _settings()
    mode = "guruh" if ntf.uses_group_workflow(st) else (
        "test (lichka)" if ntf.uses_private_notify(st) else "guruh"
    )
    lines = [
        "⚙️ <b>Bot sozlamalari</b>",
        f"Rejim: <b>{mode}</b>",
        f"SETUP_MODE: <code>{st.setup_mode}</code>",
        f"REVIEW_GROUP_ID: <code>{st.review_group_id or '—'}</code>",
        f"RETURN_GROUP_ID: <code>{st.return_group_id or '—'}</code>",
        f"Adminlar: <code>{', '.join(str(x) for x in sorted(st.admin_id_set()))}</code>",
    ]
    if st.review_group_id:
        try:
            chat = await bot.get_chat(st.review_group_id)
            lines.append(f"Guruh nomi: <b>{html.escape(chat.title or '—')}</b>")
        except Exception as exc:
            lines.append(f"⚠️ Guruhga ulanish: <code>{html.escape(str(exc)[:120])}</code>")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("pingroup"))
async def cmd_pingroup(message: Message, bot: Bot) -> None:
    if not _is_admin(message.from_user.id):
        return
    st = _settings()
    if not st.review_group_id:
        await message.answer("REVIEW_GROUP_ID o‘rnatilmagan.")
        return
    try:
        msg = await bot.send_message(
            st.review_group_id,
            "✅ <b>Test</b> — bot guruhga xabar yubora oladi.",
            parse_mode="HTML",
        )
        await message.answer(
            f"✅ Guruhga yuborildi.\n"
            f"ID: <code>{st.review_group_id}</code>\n"
            f"Xabar: #{msg.message_id}",
            parse_mode="HTML",
        )
    except Exception as exc:
        await message.answer(
            f"❌ Guruhga yuborib bo‘lmadi.\n"
            f"ID: <code>{st.review_group_id}</code>\n"
            f"Sabab: <code>{html.escape(str(exc)[:200])}</code>\n\n"
            "Bot guruhda bormi? Admin huquqi bormi?",
            parse_mode="HTML",
        )


@router.message(Command("groupid"))
async def cmd_groupid(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    chat = message.chat
    if chat.type not in ("group", "supergroup"):
        await message.answer(
            "Bu buyruq <b>guruh ichida</b> ishlatiladi.\n"
            "Guruhga botni qo‘shing va u yerda /groupid yuboring.",
            parse_mode="HTML",
        )
        return
    await message.answer(
        f"📋 Guruh: <b>{html.escape(chat.title or '—')}</b>\n"
        f"🆔 ID: <code>{chat.id}</code>\n\n"
        "Railway Variables:\n"
        f"<code>REVIEW_GROUP_ID={chat.id}</code>\n"
        f"<code>RETURN_GROUP_ID={chat.id}</code>",
        parse_mode="HTML",
    )


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    uid = message.from_user.id
    name = operator_display_name(uid) if is_team_member(uid) else (message.from_user.full_name or "—")
    await message.answer(
        f"👤 {name}\n🆔 <code>{uid}</code>",
        parse_mode="HTML",
    )


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    uid = message.from_user.id
    if not is_team_member(uid):
        await message.answer(_staff_denied(uid), parse_mode="HTML")
        return
    welcome = (
        "Kanstik tekshiruv botiga xush kelibsiz.\n\n"
        "Teruvchi sifatida yukni tekshiruvga yuborish uchun tugmani bosing."
    )
    try:
        st = _settings()
        extra = ""
        if ntf.uses_private_notify(st):
            extra = (
                "\n\n🧪 <b>Test rejim</b> — tekshiruv xabarlari hozircha "
                "<b>admin lichkasiga</b> ketadi (guruh emas).\n"
                "Guruhga yuborish: Railway da <code>REVIEW_GROUP_ID</code> qo‘ying."
            )
        elif ntf.uses_group_workflow(st):
            extra = (
                f"\n\n📡 <b>Guruh rejimi</b>\n"
                f"Tekshiruv guruhi: <code>{st.review_group_id}</code>\n"
                f"Teruvchi guruhi: <code>{st.return_group_id or st.review_group_id}</code>"
            )

        if SessionLocal is None:
            await message.answer(
                welcome + extra + "\n\n⚠️ Bazaga ulanish kutilmoqda. 1 daqiqadan keyin qayta /start.",
                reply_markup=picker_menu_kb(),
                parse_mode="HTML",
            )
            return

        async with require_session_local()() as session:
            user = await svc.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name or "",
                admin_ids=st.admin_id_set(),
            )

        if user.role == UserRole.admin:
            extra += "\n\n👑 <b>Admin</b> — /daily, /monthly, /navbat"

        await message.answer(
            welcome + extra,
            reply_markup=picker_menu_kb(),
            parse_mode="HTML",
        )
    except Exception as exc:
        log.exception("cmd_start failed user=%s", message.from_user.id)
        err = html.escape(str(exc).split("\n", maxsplit=1)[0][:200])
        await message.answer(
            f"{welcome}\n\n⚠️ DB: {err}",
            reply_markup=picker_menu_kb(),
        )


@router.message(F.text == "📦 Tekshiruvga yuborish")
async def picker_start(message: Message, state: FSMContext) -> None:
    if message.chat.type != "private":
        return
    if not is_team_member(message.from_user.id):
        await message.answer(_staff_denied(message.from_user.id), parse_mode="HTML")
        return
    await state.set_state(PickerStates.invoice)
    await message.answer("📄 Faktura raqamini kiriting:")


@router.message(PickerStates.invoice)
async def picker_invoice(message: Message, state: FSMContext) -> None:
    inv = (message.text or "").strip()
    if not inv:
        await message.answer("Faktura raqamini yozing.")
        return
    await state.update_data(invoice_number=inv)
    await state.set_state(PickerStates.cargo_photo)
    await message.answer("📸 Terilgan yuk rasmini yuboring:")


@router.message(PickerStates.cargo_photo, F.photo)
async def picker_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    st = _settings()
    data = await state.get_data()
    photo = message.photo[-1]
    sent = None
    try:
        async with require_session_local()() as session:
            user = await svc.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name or "",
                admin_ids=st.admin_id_set(),
            )
            insp = await svc.create_inspection(
                session,
                invoice_number=data["invoice_number"],
                picker=user,
                cargo_photo_file_id=photo.file_id,
            )
            text = svc.pending_inspection_text(insp)
            targets = ntf.review_target_chats(st)
            log.info("picker_photo insp=%s targets=%s", insp.id, targets)
            sent = await ntf.send_photo_notice(
                bot,
                chat_ids=targets,
                photo_file_id=photo.file_id,
                caption=text,
                reply_markup=start_review_kb(insp.id, insp.invoice_number),
            )
            if sent:
                insp.review_chat_id, insp.review_group_message_id = sent
            await session.commit()

        await state.clear()
        if not sent:
            await message.answer(
                "⚠️ <b>Guruhga yuborilmadi!</b>\n\n"
                "Tekshiring:\n"
                "1️⃣ Bot tekshiruv guruhiga qo‘shilganmi?\n"
                "2️⃣ Railway: <code>REVIEW_GROUP_ID=-100…</code> to‘g‘rimi?\n"
                "3️⃣ Guruhda <code>/groupid</code> yuboring — ID ni ko‘rasiz\n\n"
                f"ID: #{insp.id} | Faktura: {insp.invoice_number} bazada saqlandi.",
                parse_mode="HTML",
                reply_markup=picker_menu_kb(),
            )
            return
        dest = "tekshiruv guruhiga" if ntf.uses_group_workflow(st) else (
            "tekshiruvchi lichkasiga" if ntf.uses_private_notify(st) else "tekshiruv guruhiga"
        )
        await message.answer(
            f"✅ Tekshiruvchi ga yuborildi ({dest}).\n"
            f"ID: #{insp.id} | Faktura: {insp.invoice_number}\n\n"
            "⏳ Kutilmoqda — tekshiruvchi qabul qilganda xabar olasiz.",
            reply_markup=picker_menu_kb(),
        )
    except Exception as exc:
        log.exception("picker_photo failed user=%s", message.from_user.id)
        await state.clear()
        err = html.escape(str(exc).split("\n", maxsplit=1)[0][:180])
        await message.answer(
            f"⚠️ Yuk yuborilmadi.\n<code>{err}</code>\n\nQayta urinib ko‘ring.",
            parse_mode="HTML",
        )


@router.message(PickerStates.cargo_photo)
async def picker_photo_required(message: Message) -> None:
    await message.answer("Iltimos, rasm yuboring (foto).")


def _review_chat(insp, callback: CallbackQuery, st) -> int:
    if insp.review_chat_id:
        return int(insp.review_chat_id)
    if ntf.uses_private_notify(st):
        return callback.message.chat.id
    return st.review_group_id


async def _notify_picker(bot: Bot, picker_tg: int | None, text: str) -> None:
    if not picker_tg:
        return
    try:
        await bot.send_message(picker_tg, text, parse_mode="HTML")
    except Exception:
        log.exception("picker notify failed tg=%s", picker_tg)


@router.callback_query(F.data.startswith("rev:start:"))
async def cb_start_review(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    async with require_session_local()() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await callback.answer("Topilmadi", show_alert=True)
            return
        user = await svc.get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name or "",
            admin_ids=st.admin_id_set(),
        )
        allowed, reason = await svc.can_start_review(
            session,
            insp,
            actor_telegram_id=callback.from_user.id,
            admin_ids=st.admin_id_set(),
        )
        if not allowed:
            await callback.answer(reason, show_alert=True)
            return
        if user.role == UserRole.picker:
            user.role = UserRole.reviewer
        ok = await svc.start_review(session, insp, user)
        if not ok:
            await callback.answer("Allaqachon olingan yoki yakunlangan", show_alert=True)
            return
        await session.refresh(insp)
        text = svc.in_review_text(insp)
        reviewer_tg = callback.from_user.id
        wait = svc.wait_label(insp, insp.review_started_at)

        if ntf.uses_group_workflow(st):
            group_chat = _review_chat(insp, callback, st)
            group_msg = insp.review_group_message_id or callback.message.message_id
            await ntf.edit_photo_caption(
                bot,
                chat_id=group_chat,
                message_id=group_msg,
                caption=svc.group_claimed_text(insp),
                reply_markup=None,
            )
            dm = await ntf.send_photo_notice(
                bot,
                chat_ids=[reviewer_tg],
                photo_file_id=insp.cargo_photo_file_id,
                caption=text,
                reply_markup=review_actions_kb(insp.id),
            )
            if dm:
                insp.reviewer_dm_chat_id, insp.reviewer_dm_message_id = dm
        else:
            chat_id = _review_chat(insp, callback, st)
            msg_id = insp.review_group_message_id or callback.message.message_id
            if not await ntf.edit_photo_caption(
                bot,
                chat_id=chat_id,
                message_id=msg_id,
                caption=text,
                reply_markup=review_actions_kb(insp.id),
            ):
                await ntf.send_text_notice(bot, chat_ids=[chat_id], text=text)

        picker_tg = await svc.picker_telegram_id(session, insp)
        await _notify_picker(
            bot,
            picker_tg,
            f"🔍 Tekshiruvchi qabul qildi.\n"
            f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
            f"⏳ Kutish vaqti: <b>{wait}</b>",
        )
        await session.commit()
    await callback.answer(f"Qabul qilindi. Kutish: {wait}")


def _reviewer_controls_chat(insp, callback: CallbackQuery, st) -> bool:
    if not ntf.uses_group_workflow(st):
        return True
    if insp.reviewer_dm_message_id and insp.reviewer_dm_chat_id:
        return (
            callback.message.chat.id == int(insp.reviewer_dm_chat_id)
            and callback.message.message_id == int(insp.reviewer_dm_message_id)
        )
    return callback.message.chat.type == "private"


@router.callback_query(F.data.startswith("rev:ok:"))
async def cb_approve(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    async with require_session_local()() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await callback.answer("Topilmadi", show_alert=True)
            return
        if not _reviewer_controls_chat(insp, callback, st):
            await callback.answer("Tekshiruvni lichkangizdagi xabardan tasdiqlang", show_alert=True)
            return
        ok = await svc.approve_inspection(session, insp)
        if not ok:
            await callback.answer("Holat mos emas", show_alert=True)
            return
        await session.refresh(insp)
        text = svc.approved_text(insp)

        if ntf.uses_group_workflow(st):
            await ntf.edit_photo_caption(
                bot,
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=text,
                reply_markup=None,
            )
            if insp.review_chat_id and insp.review_group_message_id:
                nav = svc.group_nav_done_text(insp)
                if int(insp.review_group_message_id) != callback.message.message_id:
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.review_chat_id),
                        message_id=int(insp.review_group_message_id),
                        caption=nav,
                        reply_markup=None,
                    )
        else:
            chat_id = _review_chat(insp, callback, st)
            msg_id = insp.review_group_message_id or callback.message.message_id
            if not await ntf.edit_photo_caption(
                bot,
                chat_id=chat_id,
                message_id=msg_id,
                caption=text,
                reply_markup=None,
            ):
                await ntf.send_text_notice(bot, chat_ids=[chat_id], text=text)

        picker_tg = await svc.picker_telegram_id(session, insp)
        await _notify_picker(
            bot,
            picker_tg,
            f"✅ Tasdiqlandi.\n📄 Faktura: <b>{insp.invoice_number}</b>",
        )
    await callback.answer("Tasdiqlandi")


@router.callback_query(F.data.startswith("rev:bad:"))
async def cb_reject_start(callback: CallbackQuery) -> None:
    insp_id = int(callback.data.split(":")[-1])
    await callback.message.answer(
        "❌ Xato turini tanlang:",
        reply_markup=error_types_kb(insp_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rev:err:"))
async def cb_error_type(callback: CallbackQuery, state: FSMContext) -> None:
    _, _, insp_id, err_val = callback.data.split(":", 3)
    await state.set_state(ReviewerStates.error_comment)
    await state.update_data(inspection_id=int(insp_id), error_type=err_val)
    await callback.message.answer(
        "📝 Xato haqida qisqa izoh yozing yoki 🎤 ovozli xabar yuboring:"
    )
    await callback.answer()


async def _finalize_return(
    message: Message,
    state: FSMContext,
    bot: Bot,
    data: dict,
) -> None:
    st = _settings()
    insp_id = int(data["inspection_id"])
    err_type = ErrorType(data["error_type"])

    try:
        async with require_session_local()() as session:
            insp = await svc.get_inspection(session, insp_id)
            if not insp:
                await message.answer("Inspection topilmadi.")
                await state.clear()
                return
            ok = await svc.return_inspection(
                session,
                insp,
                error_type=err_type,
                error_comment=data["error_comment"],
            )
            if not ok:
                await message.answer("Holat mos emas. Avval tekshiruvni boshlang.")
                await state.clear()
                return

            err = await svc.get_inspection_error(session, insp_id)
            if not err:
                await message.answer("Xato saqlanmadi. Qayta urinib ko‘ring.")
                await state.clear()
                return

            await session.refresh(insp)
            text = svc.returned_text(insp, err)
            fix_caption = text + "\n\n👇 Tuzatgach tugmani bosing:"
            voice_id = data.get("error_voice_file_id")

            if ntf.uses_group_workflow(st):
                if insp.reviewer_dm_chat_id and insp.reviewer_dm_message_id:
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.reviewer_dm_chat_id),
                        message_id=int(insp.reviewer_dm_message_id),
                        caption=text + "\n\n<i>Xato qayd etildi — teruvchiga yuborildi</i>",
                        reply_markup=None,
                    )
                group_ret = await ntf.send_photo_notice(
                    bot,
                    chat_ids=ntf.error_group_chats(st),
                    photo_file_id=insp.cargo_photo_file_id,
                    caption=fix_caption,
                    reply_markup=picker_fix_kb(insp.id),
                )
                picker_tg = await svc.picker_telegram_id(session, insp)
                picker_ret = None
                if picker_tg:
                    picker_ret = await ntf.send_photo_notice(
                        bot,
                        chat_ids=[picker_tg],
                        photo_file_id=insp.cargo_photo_file_id,
                        caption=fix_caption,
                        reply_markup=picker_fix_kb(insp.id),
                    )
                    if voice_id:
                        await ntf.send_voice_notice(
                            bot,
                            chat_ids=[picker_tg],
                            voice_file_id=voice_id,
                            caption="📝 Izoh (ovoz)",
                        )
                if group_ret:
                    insp.return_chat_id, insp.return_group_message_id = group_ret
                if picker_ret:
                    insp.picker_return_chat_id, insp.picker_return_message_id = picker_ret
                if voice_id and group_ret:
                    await ntf.send_voice_notice(
                        bot,
                        chat_ids=ntf.error_group_chats(st),
                        voice_file_id=voice_id,
                        caption="📝 Izoh (ovoz)",
                    )
                if insp.review_chat_id and insp.review_group_message_id:
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.review_chat_id),
                        message_id=int(insp.review_group_message_id),
                        caption=svc.group_error_sent_text(insp),
                        reply_markup=None,
                    )
            else:
                ret_chats = ntf.unique_chat_ids(ntf.return_target_chats(st))
                picker_tg = await svc.picker_telegram_id(session, insp)
                targets = list(ret_chats)
                if picker_tg and picker_tg not in ret_chats:
                    targets.append(picker_tg)
                targets = ntf.unique_chat_ids(targets)
                ret = await ntf.send_photo_notice(
                    bot,
                    chat_ids=targets,
                    photo_file_id=insp.cargo_photo_file_id,
                    caption=fix_caption,
                    reply_markup=picker_fix_kb(insp.id),
                )
                if voice_id:
                    await ntf.send_voice_notice(
                        bot,
                        chat_ids=targets,
                        voice_file_id=voice_id,
                        caption="📝 Izoh (ovoz)",
                    )
                if ret:
                    insp.return_group_message_id = ret[1]
                    insp.return_chat_id = ret[0]
                review_chat = insp.review_chat_id or message.chat.id
                done_note = "Teruvchiga yuborildi (test rejim)."
                if not await ntf.edit_photo_caption(
                    bot,
                    chat_id=review_chat,
                    message_id=insp.review_group_message_id,
                    caption=text + f"\n\n<i>{done_note}</i>",
                    reply_markup=None,
                ):
                    await ntf.send_text_notice(bot, chat_ids=[review_chat], text=text)
            await session.commit()

        await state.clear()
        await message.answer("✅ Xato qayd etildi.")
    except Exception:
        log.exception("finalize_return failed insp=%s", insp_id)
        await message.answer(
            "⚠️ Xato saqlanmadi. Qayta urinib ko‘ring yoki admin bilan bog‘laning."
        )
        await state.clear()


@router.message(ReviewerStates.error_comment, F.voice)
async def reviewer_comment_voice(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    data["error_comment"] = "🎤 Ovozli izoh"
    data["error_voice_file_id"] = message.voice.file_id
    await _finalize_return(message, state, bot, data)


@router.message(ReviewerStates.error_comment)
async def reviewer_comment(message: Message, state: FSMContext, bot: Bot) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Izoh yozing yoki ovozli xabar yuboring.")
        return
    data = await state.get_data()
    data["error_comment"] = comment
    data["error_voice_file_id"] = None
    await _finalize_return(message, state, bot, data)


@router.callback_query(F.data.startswith("fix:done:"))
async def cb_fix_done(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    try:
        async with require_session_local()() as session:
            insp = await svc.get_inspection(session, insp_id)
            if not insp:
                await callback.answer("Topilmadi", show_alert=True)
                return
            picker_tg = await svc.picker_telegram_id(session, insp)
            if picker_tg != callback.from_user.id and callback.from_user.id not in st.admin_id_set():
                await callback.answer("Faqat teruvchi tuzatganini belgilaydi", show_alert=True)
                return
            ok = await svc.submit_fix(session, insp)
            if not ok:
                await callback.answer("Allaqachon yuborilgan yoki holat mos emas", show_alert=True)
                return
            await session.refresh(insp)
            confirm_text = svc.fix_submitted_text(insp)

            if ntf.uses_group_workflow(st):
                await ntf.edit_photo_caption(
                    bot,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    caption=confirm_text + "\n\n<i>Tekshiruvchi guruhida tasdiqlanadi</i>",
                    reply_markup=None,
                )
                if (
                    insp.picker_return_chat_id
                    and insp.picker_return_message_id
                    and (
                        int(insp.picker_return_chat_id) != callback.message.chat.id
                        or int(insp.picker_return_message_id) != callback.message.message_id
                    )
                ):
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.picker_return_chat_id),
                        message_id=int(insp.picker_return_message_id),
                        caption=confirm_text + "\n\n<i>Guruhda tasdiqlanadi</i>",
                        reply_markup=None,
                    )
                confirm = await ntf.send_photo_notice(
                    bot,
                    chat_ids=ntf.confirm_group_chats(st),
                    photo_file_id=insp.cargo_photo_file_id,
                    caption=confirm_text,
                    reply_markup=reviewer_confirm_fix_kb(insp.id),
                )
                if confirm:
                    insp.confirm_chat_id, insp.confirm_message_id = confirm
                if insp.review_chat_id and insp.review_group_message_id:
                    await ntf.edit_photo_caption(
                        bot,
                        chat_id=int(insp.review_chat_id),
                        message_id=int(insp.review_group_message_id),
                        caption=svc.group_fix_pending_text(insp),
                        reply_markup=None,
                    )
            else:
                await ntf.edit_photo_caption(
                    bot,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    caption=confirm_text,
                    reply_markup=reviewer_confirm_fix_kb(insp.id),
                )
                reviewer_tg = await svc.reviewer_telegram_id(session, insp)
                if reviewer_tg and reviewer_tg != callback.message.chat.id:
                    await ntf.send_photo_notice(
                        bot,
                        chat_ids=[reviewer_tg],
                        photo_file_id=insp.cargo_photo_file_id,
                        caption=confirm_text,
                        reply_markup=reviewer_confirm_fix_kb(insp.id),
                    )
            await session.commit()
        await callback.answer("Tekshiruvchi tasdig'i so'raldi ✅")
    except Exception:
        log.exception("fix:done failed insp=%s", insp_id)
        await callback.answer("Xato yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("fix:ok:"))
async def cb_fix_ok(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    try:
        async with require_session_local()() as session:
            insp = await svc.get_inspection(session, insp_id)
            if not insp:
                await callback.answer("Topilmadi", show_alert=True)
                return
            if not await _can_confirm_fix(
                session, insp, callback.from_user.id, st.admin_id_set()
            ):
                await callback.answer("Faqat tekshiruvchi tasdiqlaydi", show_alert=True)
                return
            if (
                ntf.uses_group_workflow(st)
                and insp.confirm_message_id
                and callback.message.message_id != int(insp.confirm_message_id)
            ):
                await callback.answer("Eski xabar — yangisidan tasdiqlang", show_alert=True)
                return
            ok = await svc.confirm_fix(session, insp)
            if not ok:
                await callback.answer("Holat mos emas", show_alert=True)
                return
            await session.refresh(insp)
            full_text = svc.fix_confirmed_text(insp)

            if ntf.uses_group_workflow(st):
                confirm_k = _msg_key(callback.message.chat.id, callback.message.message_id)
                await _apply_group_edits(
                    bot,
                    [
                        (confirm_k, full_text, None),
                        (
                            _msg_key(insp.review_chat_id, insp.review_group_message_id),
                            svc.group_nav_done_text(insp, via_fix=True),
                            None,
                        ),
                        (
                            _msg_key(insp.return_chat_id, insp.return_group_message_id),
                            svc.group_error_fixed_text(insp),
                            None,
                        ),
                        (
                            _msg_key(insp.picker_return_chat_id, insp.picker_return_message_id),
                            full_text,
                            None,
                        ),
                    ],
                )
            else:
                await ntf.edit_photo_caption(
                    bot,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    caption=full_text,
                    reply_markup=None,
                )
                if insp.review_chat_id and insp.review_group_message_id:
                    if (
                        int(insp.review_chat_id) != callback.message.chat.id
                        or int(insp.review_group_message_id) != callback.message.message_id
                    ):
                        await ntf.edit_photo_caption(
                            bot,
                            chat_id=int(insp.review_chat_id),
                            message_id=int(insp.review_group_message_id),
                            caption=full_text,
                            reply_markup=None,
                        )

            picker_tg = await svc.picker_telegram_id(session, insp)
            await _notify_picker(
                bot,
                picker_tg,
                f"✅ Tekshiruvchi tasdiqladi.\n📄 Faktura: <b>{insp.invoice_number}</b>",
            )
            insp.confirm_message_id = None
            insp.confirm_chat_id = None
            await session.commit()
        await callback.answer("Tasdiqlandi ✅")
    except Exception:
        log.exception("fix:ok failed insp=%s", insp_id)
        await callback.answer("Xato yuz berdi", show_alert=True)


@router.callback_query(F.data.startswith("fix:bad:"))
async def cb_fix_bad(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    try:
        async with require_session_local()() as session:
            insp = await svc.get_inspection(session, insp_id)
            if not insp:
                await callback.answer("Topilmadi", show_alert=True)
                return
            if not await _can_confirm_fix(
                session, insp, callback.from_user.id, st.admin_id_set()
            ):
                await callback.answer("Faqat tekshiruvchi tasdiqlaydi", show_alert=True)
                return
            if (
                ntf.uses_group_workflow(st)
                and insp.confirm_message_id
                and callback.message.message_id != int(insp.confirm_message_id)
            ):
                await callback.answer("Eski xabar — yangisidan javob bering", show_alert=True)
                return
            ok = await svc.reject_fix_submission(session, insp)
            if not ok:
                await callback.answer("Holat mos emas", show_alert=True)
                return
            err = await svc.get_inspection_error(session, insp_id)
            if not err:
                await callback.answer("Xato ma'lumoti topilmadi", show_alert=True)
                return
            await session.refresh(insp)
            fix_text = svc.returned_text(insp, err) + "\n\n👇 Qayta tuzatib tugmani bosing:"
            closed = (
                f"❌ <b>Tasdiqlanmadi</b> · #{insp.id}\n"
                f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
                f"<i>Teruvchi qayta tuzatadi</i>"
            )

            if ntf.uses_group_workflow(st):
                await _apply_group_edits(
                    bot,
                    [
                        (
                            _msg_key(callback.message.chat.id, callback.message.message_id),
                            closed,
                            None,
                        ),
                        (
                            _msg_key(insp.return_chat_id, insp.return_group_message_id),
                            fix_text,
                            picker_fix_kb(insp.id),
                        ),
                        (
                            _msg_key(insp.picker_return_chat_id, insp.picker_return_message_id),
                            fix_text,
                            picker_fix_kb(insp.id),
                        ),
                        (
                            _msg_key(insp.review_chat_id, insp.review_group_message_id),
                            svc.group_error_sent_text(insp),
                            None,
                        ),
                    ],
                )
            else:
                await ntf.edit_photo_caption(
                    bot,
                    chat_id=callback.message.chat.id,
                    message_id=callback.message.message_id,
                    caption=fix_text,
                    reply_markup=picker_fix_kb(insp.id),
                )
                picker_tg = await svc.picker_telegram_id(session, insp)
                if picker_tg and picker_tg != callback.message.chat.id:
                    await _notify_picker(
                        bot,
                        picker_tg,
                        f"❌ Yana xato bor.\n📄 Faktura: {insp.invoice_number}\n"
                        "Qayta tuzating va tugmani bosing.",
                    )
            insp.confirm_message_id = None
            insp.confirm_chat_id = None
            await session.commit()
        await callback.answer("Teruvchi qayta tuzatadi")
    except Exception:
        log.exception("fix:bad failed insp=%s", insp_id)
        await callback.answer("Xato yuz berdi", show_alert=True)


@router.message(Command("navbat"))
async def cmd_navbat(message: Message) -> None:
    if SessionLocal is None:
        await message.answer("Baza tayyor emas.")
        return
    async with require_session_local()() as session:
        pending = await svc.list_pending(session)
    if not pending:
        await message.answer("📋 Navbat bo'sh — kutilayotgan tekshiruv yo'q ✅")
        return
    lines = ["📋 <b>Kutilayotgan tekshiruvlar</b> (eng eskisi birinchi):\n"]
    for i, insp in enumerate(pending[:15], 1):
        mins = svc.wait_minutes(insp)
        flag = svc.wait_flag(mins)
        wait = svc.wait_label(insp)
        lines.append(
            f"{flag} {i}. #{insp.id} faktura <b>{insp.invoice_number}</b> — "
            f"{wait} ({insp.picker_name})"
        )
    if len(pending) > 15:
        lines.append(f"\n... yana {len(pending) - 15} ta")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("daily"))
async def cmd_daily(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    async with require_session_local()() as session:
        text = await svc.daily_report(session)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("monthly"))
async def cmd_monthly(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    async with require_session_local()() as session:
        text = await svc.monthly_report(session)
    await message.answer(text, parse_mode="HTML")
