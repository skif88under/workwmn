import asyncio
import json
import logging

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from config import BOT_TOKEN
from core.loader import (
    load_modules,
    )
from core.user_logger import (
    init_db,
    register_user,
    get_welcome_message_id,
    save_welcome_message_id,
)


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
            user_id = message.from_user.id
            logger.info("Получена команда /start от user_id=%s", user_id)

            await register_user(bot, message.from_user)

            # Если приветствие уже отправлялось, копируем его в чат.
            # Так повторный /start не загружает изображение заново.
            saved_message_id = await get_welcome_message_id(user_id)

            if saved_message_id:
                try:
                    copied_message = await bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=message.chat.id,
                        message_id=saved_message_id,
                        reply_markup=menu
                    )
                    # Сохраняем ID свежей копии: она станет актуальным приветствием.
                    await save_welcome_message_id(
                        user_id,
                        copied_message.message_id
                    )
                    return

                except TelegramBadRequest as error:
                    logger.warning(
                        "Сохранённое приветствие недоступно для user_id=%s: %s. "
                        "Отправляю новое.",
                        user_id,
                        error
                    )

            # Первое приветствие или восстановление удалённого сообщения.
            sent_message = None

            if welcome_image:
                image_path = Path(__file__).parent / welcome_image

                if image_path.is_file():
                    photo = FSInputFile(image_path)
                    sent_message = await message.answer_photo(
                        photo=photo,
                        caption=welcome_text,
                        reply_markup=menu
                    )
                else:
                    logger.error("Изображение приветствия не найдено: %s", image_path)

            if sent_message is None:
                sent_message = await message.answer(
                    welcome_text,
                    reply_markup=menu
                )

            await save_welcome_message_id(user_id, sent_message.message_id)

        # Не вызываем delete_webhook при каждом старте:
        # этот лишний запрос тоже может попасть под Telegram flood control.
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
