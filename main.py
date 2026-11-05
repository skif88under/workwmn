import asyncio
import json

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from config import BOT_TOKEN
from core.loader import load_modules
from core.user_logger import init_db, register_user


def load_settings():
    settings_path = Path(__file__).parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as file:
        settings = json.load(file)

    welcome_text = settings.get(
        "welcome_text",
        "Привет! Добро пожаловать."
    )

    if not isinstance(welcome_text, str):
        raise ValueError("welcome_text должен быть строкой")

    return settings


def build_menu(menu_items):
    buttons = []

    for item in menu_items:
        buttons.append(
            InlineKeyboardButton(
                text=item["text"],
                callback_data=item["callback_data"]
            )
        )

    # По две кнопки в строке
    keyboard = [
        buttons[i:i + 2]
        for i in range(0, len(buttons), 2)
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def main():
    settings = load_settings()
    welcome_text = settings["welcome_text"]

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        await init_db()

        # Загружаем дополнительные модули
        menu_items = await load_modules(bot, dp)

        # Создаём меню
        menu = build_menu(menu_items) if menu_items else None

        @dp.message(CommandStart())
        async def start_handler(message: Message):
            await register_user(bot, message.from_user)

            await message.answer(
                welcome_text,
                reply_markup=menu
            )

        print("Бот успешно запущен!")

        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
