import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ErrorEvent

from app.bot.handlers import router
from app.config import get_settings
from app.db.session import SessionLocal
from sqlalchemy import text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


async def main() -> None:
    settings = get_settings()
    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    me = await bot.get_me()
    log.info(
        "Bot started: @%s id=%s setup_mode=%s admins=%s",
        me.username,
        me.id,
        settings.setup_mode,
        sorted(settings.admin_id_set()),
    )

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        log.info("Database connection OK")
    except Exception as exc:
        log.error("Database connection FAILED: %s", exc)

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

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
