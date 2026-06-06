from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from app.constants import ERROR_TYPE_LABELS, ErrorType


def picker_menu_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📦 Tekshiruvga yuborish")]],
        resize_keyboard=True,
    )


def start_review_kb(inspection_id: int, invoice: str = "") -> InlineKeyboardMarkup:
    inv = f" #{invoice}" if invoice else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅{inv} — Qabul qilib boshlash",
                    callback_data=f"rev:start:{inspection_id}",
                )
            ]
        ]
    )


def review_actions_kb(inspection_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ To'g'ri", callback_data=f"rev:ok:{inspection_id}"),
                InlineKeyboardButton(text="❌ Xato topildi", callback_data=f"rev:bad:{inspection_id}"),
            ]
        ]
    )


def error_types_kb(inspection_id: int) -> InlineKeyboardMarkup:
    rows = []
    for i, (et, label) in enumerate(ERROR_TYPE_LABELS.items(), 1):
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{i}. {label}",
                    callback_data=f"rev:err:{inspection_id}:{et.value}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)
