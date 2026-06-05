from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.bot.keyboards import error_types_kb, picker_menu_kb, review_actions_kb, start_review_kb
from app.bot.states import PickerStates, ReviewerStates
from app.config import get_settings
from app.constants import ErrorType
from app.db.session import SessionLocal
from app.services import inspection as svc

log = logging.getLogger(__name__)
router = Router()
settings = get_settings()


def _is_admin(uid: int) -> bool:
    return uid in settings.admin_id_set()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    async with SessionLocal() as session:
        await svc.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name or "",
            admin_ids=settings.admin_id_set(),
        )
    await message.answer(
        "Kanstik tekshiruv botiga xush kelibsiz.\n\n"
        "Teruvchi sifatida yukni tekshiruvga yuborish uchun tugmani bosing.",
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
    data = await state.get_data()
    photo = message.photo[-1]
    async with SessionLocal() as session:
        user = await svc.get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name or "",
            admin_ids=settings.admin_id_set(),
        )
        insp = await svc.create_inspection(
            session,
            invoice_number=data["invoice_number"],
            picker=user,
            cargo_photo_file_id=photo.file_id,
        )
        text = svc.new_inspection_text(insp)
        msg = await bot.send_photo(
            settings.review_group_id,
            photo.file_id,
            caption=text,
            reply_markup=start_review_kb(insp.id),
            parse_mode="HTML",
        )
        insp.review_group_message_id = msg.message_id
        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ Tekshiruvga yuborildi.\nID: #{insp.id}",
        reply_markup=picker_menu_kb(),
    )


@router.message(PickerStates.cargo_photo)
async def picker_photo_required(message: Message) -> None:
    await message.answer("Iltimos, rasm yuboring (foto).")


@router.callback_query(F.data.startswith("rev:start:"))
async def cb_start_review(callback: CallbackQuery, bot: Bot) -> None:
    insp_id = int(callback.data.split(":")[-1])
    async with SessionLocal() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await callback.answer("Topilmadi", show_alert=True)
            return
        user = await svc.get_or_create_user(
            session,
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name or "",
            admin_ids=settings.admin_id_set(),
        )
        ok = await svc.start_review(session, insp, user)
        if not ok:
            await callback.answer("Allaqachon olingan yoki yakunlangan", show_alert=True)
            return
        await session.refresh(insp)
        text = svc.in_review_text(insp)
        try:
            await bot.edit_message_caption(
                chat_id=settings.review_group_id,
                message_id=insp.review_group_message_id or callback.message.message_id,
                caption=text,
                reply_markup=review_actions_kb(insp.id),
                parse_mode="HTML",
            )
        except Exception:
            log.exception("edit caption")
    await callback.answer("Tekshiruv boshlandi")


@router.callback_query(F.data.startswith("rev:ok:"))
async def cb_approve(callback: CallbackQuery, bot: Bot) -> None:
    insp_id = int(callback.data.split(":")[-1])
    async with SessionLocal() as session:
        insp = await svc.get_inspection(session, insp_id)
        if not insp:
            await callback.answer("Topilmadi", show_alert=True)
            return
        if insp.reviewer_id and callback.from_user.id:
            pass
        ok = await svc.approve_inspection(session, insp)
        if not ok:
            await callback.answer("Holat mos emas", show_alert=True)
            return
        await session.refresh(insp)
        text = svc.approved_text(insp)
        try:
            await bot.edit_message_caption(
                chat_id=settings.review_group_id,
                message_id=insp.review_group_message_id or callback.message.message_id,
                caption=text,
                reply_markup=None,
                parse_mode="HTML",
            )
        except Exception:
            await bot.send_message(settings.review_group_id, text, parse_mode="HTML")
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
    data = await state.get_data()
    photo = message.photo[-1]
    insp_id = int(data["inspection_id"])
    err_type = ErrorType(data["error_type"])

    async with SessionLocal() as session:
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
                admin_ids=settings.admin_id_set(),
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
        ret = await bot.send_photo(
            settings.return_group_id,
            photo.file_id,
            caption=text,
            parse_mode="HTML",
        )
        await bot.send_photo(
            settings.return_group_id,
            insp.cargo_photo_file_id,
            caption="📸 Dastlabki yuk rasmi",
        )
        insp.return_group_message_id = ret.message_id
        try:
            await bot.edit_message_caption(
                chat_id=settings.review_group_id,
                message_id=insp.review_group_message_id,
                caption=text + "\n\n<i>Qayta terish guruhiga yuborildi.</i>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        await session.commit()

    await state.clear()
    await message.answer("✅ Xato qayd etildi va qayta terish guruhiga yuborildi.")


@router.message(ReviewerStates.error_photo)
async def reviewer_photo_required(message: Message) -> None:
    await message.answer("Xato rasmini yuboring (foto).")


@router.message(Command("daily"))
async def cmd_daily(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    async with SessionLocal() as session:
        text = await svc.daily_report(session)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("monthly"))
async def cmd_monthly(message: Message) -> None:
    if not _is_admin(message.from_user.id):
        return
    async with SessionLocal() as session:
        text = await svc.monthly_report(session)
    await message.answer(text, parse_mode="HTML")
