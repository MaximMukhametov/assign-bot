from __future__ import annotations

import asyncio
import logging
import os
from typing import NoReturn

from aiogram import Bot, Dispatcher
from src.assign_bot import router


logger = logging.getLogger(__name__)




async def run_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    token: str | None = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        logger.error("Переменная окружения TELEGRAM_TOKEN не установлена")
        return

    bot: Bot | None = None
    try:
        bot = Bot(token=token)
        dispatcher = Dispatcher()
        dispatcher.include_router(router)

        logger.info("Старт поллинга Telegram бота")
        await dispatcher.start_polling(bot)
    except Exception as exc:  # noqa: BLE001 - верхнеуровневая защита точки входа
        logger.exception("Критическая ошибка работы бота: %s", exc)
    finally:
        if bot is not None:
            await bot.session.close()


def main() -> NoReturn:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
