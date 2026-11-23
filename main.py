import asyncio
import json
import logging

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from config import BOT_TOKEN
from core.loader import load_modules
from core.user_logger import init_db, register_user


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)
logger = logging.getLogger(__name__)


def load_settings():
    settings_path = Path(__file__).parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as file:
        settings = json.load(file)

    return settings


def build_menu(menu_items):
    buttons = []

    for item in menu_items:
        if item.get("url"):
            button = InlineKeyboardButton(
                text=item["text"],
                url=item["url"]
            )
        else:
            button = InlineKeyboardButton(
                text=item["text"],
                callback_data=item["callback_data"]
            )

        buttons.append([button])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def main():
    settings = load_settings()

    welcome_text = settings.get(
        "welcome_text",
        "Привет! Добро пожаловать."
    )

    welcome_image = settings.get("welcome_image")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        logger.info("Инициализация базы данных...")
        await init_db()

        logger.info("Загрузка модулей...")
        menu_items = await load_modules(bot, dp)
        menu = build_menu(menu_items) if menu_items else None

        @dp.message(CommandStart())
        async def start_handler(message: Message):
            logger.info("Получена команда /start от user_id=%s", message.from_user.id)
            await register_user(bot, message.from_user)

            if welcome_image:
                image_path = Path(__file__).parent / welcome_image

                if not image_path.is_file():
                    await message.answer(
                        "Ошибка: изображение не найдено."
                    )
                    return

                photo = FSInputFile(image_path)

                await message.answer_photo(
                    photo=photo,
                    caption=welcome_text,
                    reply_markup=menu
                )

            else:
                await message.answer(
                    welcome_text,
                    reply_markup=menu
                )

        # Удаляем возможный webhook: long polling и webhook нельзя
        # использовать одновременно для одного токена.
        logger.info("Проверка и отключение webhook перед polling...")
        await bot.delete_webhook()

        logger.info("Модули загружены. Запускаю Telegram polling...")

        while True:
            try:
                await dp.start_polling(bot)
                break
            except TelegramRetryAfter as error:
                delay = error.retry_after + 2
                logger.warning(
                    "Telegram ограничил частоту запросов. Повтор через %s сек.",
                    delay
                )
                await asyncio.sleep(delay)

    except Exception:
        logger.exception("Критическая ошибка при работе бота")
        raise
    finally:
        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())
