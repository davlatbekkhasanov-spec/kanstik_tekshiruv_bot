import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent
from sqlalchemy import text

from app.config import get_settings
from app.db.bootstrap import run_migrations, setup_database
from app.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    db_url = ""
    try:
        db_url, _ = await setup_database()
        run_migrations(db_url)
    except Exception as exc:
        log.error("Database setup failed: %s", exc)

    from app.bot.handlers import router

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    log.info(
        "Bot started: @%s id=%s setup_mode=%s review_group=%s return_group=%s admins=%s db=%s",
        me.username,
        me.id,
        settings.setup_mode,
        settings.review_group_id or "—",
        settings.return_group_id or "—",
        sorted(settings.admin_id_set()),
        bool(db_url),
    )

    if SessionLocal is not None:
        try:
            async with SessionLocal() as session:
                await session.execute(text("SELECT 1"))
                await session.execute(
                    text(
                        "SELECT return_chat_id, fix_submitted_at FROM inspections LIMIT 0"
                    )
                )
            log.info("Database connection OK")
        except Exception as exc:
            log.error("Database connection FAILED: %s", exc)
            if db_url:
                try:
                    from app.db.bootstrap import ensure_inspection_schema

                    ensure_inspection_schema(db_url)
                    log.info("Schema repair attempted")
                except Exception as repair_exc:
                    log.error("Schema repair failed: %s", repair_exc)

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        log.exception("Handler error: %s", event.exception)
        upd = event.update
        if upd.message:
            try:
                await upd.message.answer(
                    "⚠️ Ichki xato. Keyinroq qayta urinib ko‘ring yoki admin bilan bog‘laning."
                )
            except Exception:
                pass
        elif upd.callback_query:
            try:
                await upd.callback_query.answer("Xato yuz berdi", show_alert=True)
            except Exception:
                pass
        return True

    from app.services.pending_refresh import run_pending_refresh

    refresh_task = asyncio.create_task(run_pending_refresh(bot))
    try:
        await dp.start_polling(bot)
    finally:
        refresh_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
