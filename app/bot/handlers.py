from __future__ import annotations

import html
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import error_types_kb, picker_menu_kb, review_actions_kb, start_review_kb
from app.bot.states import PickerStates, ReviewerStates
from app.config import get_settings
from app.constants import ErrorType, UserRole
from app.db.session import SessionLocal, require_session_local
from app.services import inspection as svc
from app.services import notify as ntf

log = logging.getLogger(__name__)
router = Router()


def _settings():
    return get_settings()


def _is_admin(uid: int) -> bool:
    return uid in _settings().admin_id_set()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
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
                "Guruh tayyor bo‘lgach: <code>SETUP_MODE=0</code>"
            )

        if SessionLocal is None:
            await message.answer(
                welcome + extra + "\n\n⚠️ Bazaga ulanish kutilmoqda. 1 daqiqadan keyin qayta /start.",
                reply_markup=picker_menu_kb(),
                parse_mode="HTML",
            )
            return

        async with require_session_local()() as session:
            await svc.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name or "",
                admin_ids=st.admin_id_set(),
            )

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
        text = svc.new_inspection_text(insp)
        sent = await ntf.send_photo_notice(
            bot,
            chat_ids=ntf.review_target_chats(st),
            photo_file_id=photo.file_id,
            caption=text,
            reply_markup=start_review_kb(insp.id),
        )
        if sent:
            insp.review_chat_id, insp.review_group_message_id = sent
        await session.commit()

    await state.clear()
    dest = "tekshiruvchi lichkasiga" if ntf.uses_private_notify(st) else "tekshiruv guruhiga"
    await message.answer(
        f"✅ Tekshiruvchi ga yuborildi ({dest}).\n"
        f"ID: #{insp.id}\n\n"
        "Tekshiruvchi qabul qilib tekshirishni boshlaydi — natijani kuting.",
        reply_markup=picker_menu_kb(),
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
    await callback.answer("Tekshiruv boshlandi")


@router.callback_query(F.data.startswith("rev:ok:"))
async def cb_approve(callback: CallbackQuery, bot: Bot) -> None:
    st = _settings()
    insp_id = int(callback.data.split(":")[-1])
    async with require_session_local()() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await callback.answer("Topilmadi", show_alert=True)
            return
        ok = await svc.approve_inspection(session, insp)
        if not ok:
            await callback.answer("Holat mos emas", show_alert=True)
            return
        await session.refresh(insp)
        text = svc.approved_text(insp)
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
    await callback.message.answer("📝 Xato haqida qisqa izoh yozing:")
    await callback.answer()


@router.message(ReviewerStates.error_comment)
async def reviewer_comment(message: Message, state: FSMContext) -> None:
    comment = (message.text or "").strip()
    if not comment:
        await message.answer("Izoh yozing.")
        return
    await state.update_data(error_comment=comment)
    await state.set_state(ReviewerStates.error_photo)
    await message.answer("📸 Xato rasmini yuboring:")


@router.message(ReviewerStates.error_photo, F.photo)
async def reviewer_error_photo(message: Message, state: FSMContext, bot: Bot) -> None:
    st = _settings()
    data = await state.get_data()
    photo = message.photo[-1]
    insp_id = int(data["inspection_id"])
    err_type = ErrorType(data["error_type"])

    async with require_session_local()() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await message.answer("Inspection topilmadi.")
            await state.clear()
            return
        if not insp.reviewer_id:
            user = await svc.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name or "",
                admin_ids=st.admin_id_set(),
            )
            insp.reviewer_id = user.id
            insp.reviewer_name = user.full_name
        ok = await svc.return_inspection(
            session,
            insp,
            error_type=err_type,
            error_comment=data["error_comment"],
            error_photo_file_id=photo.file_id,
        )
        if not ok:
            await message.answer("Holat mos emas.")
            await state.clear()
            return
        await session.refresh(insp)
        err = insp.error
        text = svc.returned_text(insp, err)
        ret_chats = ntf.return_target_chats(st)
        ret = await ntf.send_photo_notice(
            bot,
            chat_ids=ret_chats,
            photo_file_id=photo.file_id,
            caption=text,
        )
        await ntf.send_photo_notice(
            bot,
            chat_ids=ret_chats,
            photo_file_id=insp.cargo_photo_file_id,
            caption="📸 Dastlabki yuk rasmi",
        )
        if ret:
            insp.return_group_message_id = ret[1]
        review_chat = insp.review_chat_id or message.chat.id
        done_note = (
            "Qayta terish guruhiga yuborildi."
            if not ntf.uses_private_notify(st)
            else "Admin lichkasiga yuborildi (test rejim)."
        )
        await ntf.edit_photo_caption(
            bot,
            chat_id=review_chat,
            message_id=insp.review_group_message_id,
            caption=text + f"\n\n<i>{done_note}</i>",
            reply_markup=None,
        )
        await session.commit()

    await state.clear()
    await message.answer("✅ Xato qayd etildi.")


@router.message(ReviewerStates.error_photo)
async def reviewer_photo_required(message: Message) -> None:
    await message.answer("Xato rasmini yuboring (foto).")


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
