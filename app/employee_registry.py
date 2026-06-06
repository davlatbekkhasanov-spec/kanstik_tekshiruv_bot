"""Barcha botlar uchun yagona xodim → Telegram ID (Tuvalov Farrux / Pulat migratsiya)."""

from __future__ import annotations

import re

TUVALOV_FARRUX_TG_ID = 7703650930
PRIMARY_ADMIN_TG_ID = 1432810519
CANONICAL_TUVALOV = "Tuvalov Farrux"

PULAT_LEGACY_NAMES: frozenset[str] = frozenset(
    {
        "rajabboev pulat",
        "rahabboev pulat",
        "ражаббоев пулат",
        "рахаббоев пулат",
    }
)

TUVALOV_NAME_KEYS: frozenset[str] = frozenset(
    {
        "tuvalov farrux",
        "тувалов фаррух",
        "фаррух",
    }
)

TG_EMPLOYEE: dict[int, str] = {
    924612402: "Yadullaev Umid",
    5412958249: "Ravshanov Oxunjon",
    8547365654: "Ruziboev Sindor",
    6931958983: "Mustafoev Abdullo",
    6991673998: "Sagdullaev Yunus",
    5465963344: "Shernazarov Tolib",
    6001619806: "Samadov Tulqin",
    5732350707: "Toxirov Muslimbek",
    8440127425: "Ravshanov Ziyodullo",
    1432810519: "Davlatbek Khasanov",
    TUVALOV_FARRUX_TG_ID: CANONICAL_TUVALOV,
}

EMPLOYEE_NAME_ALIASES: dict[str, int] = {
    "Yadullaev Umidjon": 924612402,
    "Yadullaev Umid": 924612402,
    "Samadov To'lqin": 6001619806,
    "Samadov Tulqin": 6001619806,
    "Ravshanov Oxunjon": 5412958249,
    "Oxunjon": 5412958249,
    "Охунжон": 5412958249,
    "Ravshanov Ziyodullo": 8440127425,
    "Ravshanov_Z_": 8440127425,
    "Mustafoev Abdullo": 6931958983,
    "Abdullo Mustafoyev": 6931958983,
    "Ruziboev Sindor": 8547365654,
    "Ruziboev sindorbek": 8547365654,
    "Toxirov Muslimbek": 5732350707,
    "Тохиров Муслимбек": 5732350707,
    "Shernazarov Tolib": 5465963344,
    "Толиб Шерназаров": 5465963344,
    "Sagdullaev Yunus": 6991673998,
    "Sagdullaev": 6991673998,
    "Davlatbek Khasanov": 1432810519,
    CANONICAL_TUVALOV: TUVALOV_FARRUX_TG_ID,
    "Тувалов Фаррух": TUVALOV_FARRUX_TG_ID,
    "Тувалов Farrux": TUVALOV_FARRUX_TG_ID,
    "Rajabboev Pulat": TUVALOV_FARRUX_TG_ID,
    "Rahabboev Pulat": TUVALOV_FARRUX_TG_ID,
    "Ражаббоев Пулат": TUVALOV_FARRUX_TG_ID,
    "Рахаббоев Пулат": TUVALOV_FARRUX_TG_ID,
}

SHORT_NAME_ALIASES: dict[str, str] = {
    "охунжон": "Ravshanov Oxunjon",
    "oxunjon": "Ravshanov Oxunjon",
    "ravshanov oxunjon": "Ravshanov Oxunjon",
    "ravshanov_z_": "Ravshanov Ziyodullo",
    "ravshanov z": "Ravshanov Ziyodullo",
    "ziyodullo": "Ravshanov Ziyodullo",
    "abdullo mustafoyev": "Mustafoev Abdullo",
    "mustafoyev abdullo": "Mustafoev Abdullo",
    "mustafoev abdullo": "Mustafoev Abdullo",
    "ruziboev sindorbek": "Ruziboev Sindor",
    "sindorbek": "Ruziboev Sindor",
    "тохиров муслимбек": "Toxirov Muslimbek",
    "toxirov muslimbek": "Toxirov Muslimbek",
    "толиб шерназаров": "Shernazarov Tolib",
    "shernazarov tolib": "Shernazarov Tolib",
    "толиб": "Shernazarov Tolib",
    "tolib": "Shernazarov Tolib",
    "samadov tolqin": "Samadov To'lqin",
    "samadov to'lqin": "Samadov To'lqin",
    "to'lqin": "Samadov To'lqin",
    "sagdullaev": "Sagdullaev Yunus",
    "yunus": "Sagdullaev Yunus",
    "tuvalov farrux": CANONICAL_TUVALOV,
    "farrux": CANONICAL_TUVALOV,
    "тувалов фаррух": CANONICAL_TUVALOV,
    "rajabboev pulat": CANONICAL_TUVALOV,
}


def all_team_tg_ids() -> frozenset[int]:
    return frozenset(TG_EMPLOYEE.keys())


def is_team_member(telegram_id: int) -> bool:
    return int(telegram_id) in all_team_tg_ids()


def operator_display_name(telegram_id: int) -> str:
    return TG_EMPLOYEE.get(int(telegram_id), f"ID {telegram_id}")


def resolve_user_name(telegram_id: int, telegram_full_name: str = "") -> str:
    if is_team_member(telegram_id):
        return operator_display_name(telegram_id)
    return (telegram_full_name or "").strip() or str(telegram_id)
