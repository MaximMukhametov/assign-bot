from __future__ import annotations

import asyncio
import logging
import os
from typing import NoReturn

from aiogram import Bot, Dispatcher, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandStart
from aiogram.types import Message


logger = logging.getLogger(__name__)


router = Router(name="echo_router")


@router.message(CommandStart())
async def handle_start(message: Message) -> None:
    try:
        await message.answer("Привет! Отправь мне любой текст, и я повторю его обратно.")
    except TelegramAPIError as exc:  # network/api issues
        logger.exception("Не удалось отправить приветственное сообщение: %s", exc)


@router.message(F.text)
async def handle_echo(message: Message) -> None:
    text: str = message.text or ""
    try:
        await message.answer(text)
    except TelegramAPIError as exc:
        logger.exception("Ошибка при отправке сообщения пользователю: %s", exc)
        # Пытаемся уведомить пользователя кратко, если возможно
        try:
            await message.answer("Не удалось отправить сообщение. Попробуйте ещё раз позже.")
        except TelegramAPIError:
            # глушим вторичную ошибку отправки
            pass


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
