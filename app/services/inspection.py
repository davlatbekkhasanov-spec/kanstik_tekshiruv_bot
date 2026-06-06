from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.constants import ERROR_TYPE_LABELS, ErrorType, InspectionResult, InspectionStatus, UserRole
from app.db.models import Inspection, InspectionError, User


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz)


def fmt_dt(dt: datetime | None) -> str:
    if not dt:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(_tz()).strftime("%H:%M")


def fmt_duration(start: datetime | None, end: datetime | None) -> str:
    if not start or not end:
        return "—"
    sec = int((end - start).total_seconds())
    if sec < 60:
        return f"{sec} soniya"
    m, s = divmod(sec, 60)
    if m < 60:
        return f"{m} daqiqa {s} soniya" if s else f"{m} daqiqa"
    h, m = divmod(m, 60)
    return f"{h} soat {m} daqiqa"


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    full_name: str,
    admin_ids: set[int],
) -> User:
    role = UserRole.admin if telegram_id in admin_ids else UserRole.picker
    row = await session.scalar(select(User).where(User.telegram_id == telegram_id))
    if row:
        row.full_name = full_name or row.full_name
        if telegram_id in admin_ids:
            row.role = UserRole.admin
        await session.commit()
        return row
    user = User(telegram_id=telegram_id, full_name=full_name or str(telegram_id), role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def create_inspection(
    session: AsyncSession,
    *,
    invoice_number: str,
    picker: User,
    cargo_photo_file_id: str,
) -> Inspection:
    insp = Inspection(
        invoice_number=invoice_number.strip(),
        picker_id=picker.id,
        picker_name=picker.full_name,
        cargo_photo_file_id=cargo_photo_file_id,
        status=InspectionStatus.pending,
    )
    session.add(insp)
    await session.commit()
    await session.refresh(insp)
    return insp


async def get_inspection(session: AsyncSession, inspection_id: int) -> Inspection | None:
    return await session.scalar(
        select(Inspection).where(Inspection.id == inspection_id)
    )


async def get_inspection_error(session: AsyncSession, inspection_id: int) -> InspectionError | None:
    return await session.scalar(
        select(InspectionError).where(InspectionError.inspection_id == inspection_id)
    )


async def picker_telegram_id(session: AsyncSession, inspection: Inspection) -> int | None:
    picker = await session.get(User, inspection.picker_id)
    return picker.telegram_id if picker else None


async def can_start_review(
    session: AsyncSession,
    inspection: Inspection,
    *,
    actor_telegram_id: int,
    admin_ids: set[int],
) -> tuple[bool, str]:
    """Teruvchi o'z yukini tekshira olmaydi (admin test rejimida mumkin)."""
    picker_tg = await picker_telegram_id(session, inspection)
    if picker_tg and picker_tg == actor_telegram_id and actor_telegram_id not in admin_ids:
        return False, "Teruvchi o'z yukini tekshira olmaydi. Tekshiruvchi kuting."
    return True, ""


async def start_review(
    session: AsyncSession,
    inspection: Inspection,
    reviewer: User,
) -> bool:
    if inspection.status != InspectionStatus.pending:
        return False
    inspection.status = InspectionStatus.in_review
    inspection.reviewer_id = reviewer.id
    inspection.reviewer_name = reviewer.full_name
    inspection.review_started_at = datetime.now(_tz())
    await session.commit()
    return True


async def approve_inspection(session: AsyncSession, inspection: Inspection) -> bool:
    if inspection.status != InspectionStatus.in_review:
        return False
    inspection.status = InspectionStatus.approved
    inspection.result = InspectionResult.correct
    inspection.review_finished_at = datetime.now(_tz())
    await session.commit()
    return True


async def reviewer_telegram_id(session: AsyncSession, inspection: Inspection) -> int | None:
    if not inspection.reviewer_id:
        return None
    user = await session.get(User, inspection.reviewer_id)
    return user.telegram_id if user else None


async def submit_fix(session: AsyncSession, inspection: Inspection) -> bool:
    if inspection.status != InspectionStatus.returned:
        return False
    inspection.status = InspectionStatus.fix_submitted
    inspection.fix_submitted_at = datetime.now(_tz())
    await session.commit()
    return True


async def confirm_fix(session: AsyncSession, inspection: Inspection) -> bool:
    if inspection.status != InspectionStatus.fix_submitted:
        return False
    inspection.status = InspectionStatus.approved
    inspection.result = InspectionResult.correct
    inspection.review_finished_at = datetime.now(_tz())
    await session.commit()
    return True


async def reopen_after_fix(session: AsyncSession, inspection: Inspection) -> bool:
    if inspection.status != InspectionStatus.fix_submitted:
        return False
    inspection.status = InspectionStatus.in_review
    inspection.fix_submitted_at = None
    await session.commit()
    return True


async def return_inspection(
    session: AsyncSession,
    inspection: Inspection,
    *,
    error_type: ErrorType,
    error_comment: str,
    error_photo_file_id: str = "",
) -> bool:
    if inspection.status != InspectionStatus.in_review:
        return False
    inspection.status = InspectionStatus.returned
    inspection.result = InspectionResult.error
    inspection.review_finished_at = datetime.now(_tz())
    session.add(
        InspectionError(
            inspection_id=inspection.id,
            error_type=error_type,
            error_comment=error_comment.strip(),
            error_photo_file_id=error_photo_file_id,
        )
    )
    await session.commit()
    return True


def _as_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC")).astimezone(_tz())
    return dt.astimezone(_tz())


def wait_minutes(insp: Inspection, until: datetime | None = None) -> int:
    until = until or datetime.now(_tz())
    sec = int((until - _as_tz(insp.created_at)).total_seconds())
    return max(0, sec // 60)


def wait_label(insp: Inspection, until: datetime | None = None) -> str:
    until = until or datetime.now(_tz())
    return fmt_duration(_as_tz(insp.created_at), until)


def wait_flag(minutes: int) -> str:
    if minutes >= 10:
        return "🔴"
    if minutes >= 5:
        return "⚠️"
    return "⏳"


async def list_pending(session: AsyncSession) -> list[Inspection]:
    rows = await session.scalars(
        select(Inspection)
        .where(Inspection.status == InspectionStatus.pending)
        .order_by(Inspection.created_at.asc())
    )
    return list(rows.all())


def pending_inspection_text(insp: Inspection, *, now: datetime | None = None) -> str:
    now = now or datetime.now(_tz())
    mins = wait_minutes(insp, now)
    flag = wait_flag(mins)
    wait = wait_label(insp, now)
    return (
        "📦 <b>YANGI TEKSHIRUV</b>\n"
        "<i>Tekshiruvchi — qabul qiling va tekshiring</i>\n\n"
        f"ID: <b>#{insp.id}</b>\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Yuborgan teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>kutilmoqda</b>\n"
        f"{flag} <b>Kutilmoqda: {wait}</b>\n"
        f"🕒 Yuborilgan: <b>{fmt_dt(insp.created_at)}</b>"
    )


def new_inspection_text(insp: Inspection) -> str:
    return pending_inspection_text(insp)


def in_review_text(insp: Inspection) -> str:
    wait = wait_label(insp, insp.review_started_at)
    return (
        "🔍 <b>TEKSHIRUV BOSHLANDI</b>\n\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>{insp.reviewer_name}</b>\n"
        f"⏳ Kutish vaqti: <b>{wait}</b>\n"
        f"🕒 Boshlangan: <b>{fmt_dt(insp.review_started_at)}</b>"
    )


def approved_text(insp: Inspection) -> str:
    wait = wait_label(insp, insp.review_started_at)
    return (
        "✅ <b>TASDIQLANDI</b>\n\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>{insp.reviewer_name}</b>\n"
        f"⏳ Kutish: <b>{wait}</b>\n"
        f"⏱ Tekshiruv: <b>{fmt_duration(insp.review_started_at, insp.review_finished_at)}</b>\n"
        f"📌 Natija: <b>Xatosiz</b>"
    )


def returned_text(insp: Inspection, err: InspectionError) -> str:
    wait = wait_label(insp, insp.review_started_at)
    return (
        "🚨 <b>XATONI TUZATING</b>\n\n"
        f"ID: <b>#{insp.id}</b>\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>{insp.reviewer_name}</b>\n"
        f"⏳ Kutish: <b>{wait}</b>\n"
        f"⏱ Tekshiruv: <b>{fmt_duration(insp.review_started_at, insp.review_finished_at)}</b>\n\n"
        f"❌ Xato turi:\n<b>{ERROR_TYPE_LABELS[err.error_type]}</b>\n\n"
        f"📝 Izoh:\n{err.error_comment}"
    )


def picker_fixed_pending_text(insp: Inspection) -> str:
    return (
        "⏳ <b>Tuzatildi — tekshiruvchi tasdig'i kutilmoqda</b>\n\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>"
    )


def fix_submitted_text(insp: Inspection) -> str:
    return (
        "✅ <b>XATOLIK BARTARAF ETILDI</b>\n\n"
        "🔍 <b>Tekshiruvchi, iltimos tasdiqlang.</b>\n\n"
        f"ID: <b>#{insp.id}</b>\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>{insp.reviewer_name or '—'}</b>"
    )


def fix_confirmed_text(insp: Inspection) -> str:
    wait = wait_label(insp, insp.review_started_at)
    return (
        "✅ <b>TASDIQLANDI</b> (xato tuzatildi)\n\n"
        f"📄 Faktura: <b>{insp.invoice_number}</b>\n"
        f"👤 Teruvchi: <b>{insp.picker_name}</b>\n"
        f"🔍 Tekshiruvchi: <b>{insp.reviewer_name}</b>\n"
        f"⏳ Kutish: <b>{wait}</b>\n"
        f"📌 Natija: <b>Xato tuzatildi va tasdiqlandi</b>"
    )


async def daily_report(session: AsyncSession, day: datetime | None = None) -> str:
    tz = _tz()
    ref = day or datetime.now(tz)
    start = ref.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    rows = (
        await session.scalars(
            select(Inspection).where(Inspection.created_at >= start, Inspection.created_at < end)
        )
    ).all()
    total = len(rows)
    approved = sum(1 for r in rows if r.status == InspectionStatus.approved)
    returned = sum(1 for r in rows if r.status == InspectionStatus.returned)
    done = approved + returned
    pct = int(approved * 100 / done) if done else 0

    picker_stats: dict[str, dict[str, int]] = {}
    for r in rows:
        st = picker_stats.setdefault(r.picker_name, {"ok": 0, "bad": 0, "total": 0})
        st["total"] += 1
        if r.status == InspectionStatus.approved:
            st["ok"] += 1
        elif r.status == InspectionStatus.returned:
            st["bad"] += 1

    best = sorted(
        ((n, s["ok"], s["total"]) for n, s in picker_stats.items() if s["total"]),
        key=lambda x: (-(x[1] * 100 // x[2] if x[2] else 0), -x[1]),
    )[:3]
    worst = sorted(
        ((n, s["bad"]) for n, s in picker_stats.items() if s["bad"]),
        key=lambda x: -x[1],
    )[:3]

    err_rows = await session.execute(
        select(InspectionError.error_type, func.count())
        .join(Inspection)
        .where(Inspection.created_at >= start, Inspection.created_at < end)
        .group_by(InspectionError.error_type)
        .order_by(func.count().desc())
    )
    err_lines = [
        f"{i}. {ERROR_TYPE_LABELS.get(et, et.value)} — {cnt} ta"
        for i, (et, cnt) in enumerate(err_rows.all(), 1)
    ]

    lines = [
        "📊 <b>BUGUNGI TEKSHIRUV HISOBOTI</b>\n",
        f"📦 Jami tekshiruvga yuborilgan: <b>{total}</b>",
        f"✅ Tasdiqlangan: <b>{approved}</b>",
        f"🚨 Qaytarilgan: <b>{returned}</b>",
        f"📈 Birinchi o'tishda qabul foizi: <b>{pct}%</b>\n",
        "🏆 <b>Eng aniq teruvchilar:</b>",
    ]
    if best:
        for i, (name, ok, tot) in enumerate(best, 1):
            p = ok * 100 // tot if tot else 0
            lines.append(f"{i}. {name} — {ok} ta / {p}% xatosiz")
    else:
        lines.append("—")
    lines.append("\n⚠️ <b>Eng ko'p xato chiqqanlar:</b>")
    if worst:
        for i, (name, bad) in enumerate(worst, 1):
            lines.append(f"{i}. {name} — {bad} ta xato")
    else:
        lines.append("—")
    lines.append("\n📌 <b>Xato turlari:</b>")
    lines.extend(err_lines or ["—"])
    return "\n".join(lines)


async def monthly_report(session: AsyncSession, ref: datetime | None = None) -> str:
    tz = _tz()
    now = ref or datetime.now(tz)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)

    rows = (
        await session.scalars(
            select(Inspection).where(Inspection.created_at >= start, Inspection.created_at < end)
        )
    ).all()
    total = len(rows)
    approved = sum(1 for r in rows if r.status == InspectionStatus.approved)
    returned = sum(1 for r in rows if r.status == InspectionStatus.returned)
    done = approved + returned
    pct = int(approved * 100 / done) if done else 0

    by_picker: dict[str, dict] = {}
    for r in rows:
        st = by_picker.setdefault(
            r.picker_name,
            {"total": 0, "ok": 0, "bad": 0, "errors": {}},
        )
        st["total"] += 1
        if r.status == InspectionStatus.approved:
            st["ok"] += 1
        elif r.status == InspectionStatus.returned:
            st["bad"] += 1

    err_list = (
        await session.scalars(
            select(InspectionError)
            .join(Inspection)
            .where(Inspection.created_at >= start, Inspection.created_at < end)
        )
    ).all()
    err_totals: dict[ErrorType, int] = {}
    for err in err_list:
        insp = await session.get(Inspection, err.inspection_id)
        if not insp:
            continue
        by_picker.setdefault(
            insp.picker_name,
            {"total": 0, "ok": 0, "bad": 0, "errors": {}},
        )
        by_picker[insp.picker_name]["errors"][err.error_type] = (
            by_picker[insp.picker_name]["errors"].get(err.error_type, 0) + 1
        )
        err_totals[err.error_type] = err_totals.get(err.error_type, 0) + 1

    lines = [
        "📊 <b>OYLIK KAIZEN HISOBOTI</b>\n",
        f"📦 Jami tekshiruv: <b>{total}</b>",
        f"✅ Xatosiz o'tgan: <b>{approved}</b>",
        f"🚨 Qaytarilgan: <b>{returned}</b>",
        f"📈 Qabul foizi: <b>{pct}%</b>\n",
        "👤 <b>Xodimlar bo'yicha:</b>",
    ]
    for name, st in sorted(by_picker.items()):
        tot = st["total"]
        bad = st["bad"]
        err_pct = bad * 100 // tot if tot else 0
        top_err = "—"
        if st.get("errors"):
            et = max(st["errors"], key=st["errors"].get)
            top_err = ERROR_TYPE_LABELS.get(et, et.value)
        lines.append(
            f"• <b>{name}</b> — jami {tot}, xatosiz {st['ok']}, "
            f"xato {bad} ({err_pct}%), ko'p xato: {top_err}"
        )
    lines.append("\n📌 <b>Xato turlari reytingi:</b>")
    for i, (et, cnt) in enumerate(
        sorted(err_totals.items(), key=lambda x: -x[1])[:5], 1
    ):
        lines.append(f"{i}. {ERROR_TYPE_LABELS.get(et, et.value)} — {cnt} ta")
    return "\n".join(lines)
