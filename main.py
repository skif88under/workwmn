
import asyncio
import json

from pathlib import Path

from aiogram import Bot, Dispatcher
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


def load_settings():
    settings_path = Path(__file__).parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as file:
        settings = json.load(file)

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

    keyboard = [
        buttons[i:i + 2]
        for i in range(0, len(buttons), 2)
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


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
        await init_db()

        menu_items = await load_modules(bot, dp)

        menu = build_menu(menu_items) if menu_items else None

        @dp.message(CommandStart())
        async def start_handler(message: Message):
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

        print("Бот успешно запущен!")

        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
