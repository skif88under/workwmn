import asyncio
import json

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

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
        raise ValueError(
            "welcome_text должен быть текстовой строкой"
        )

    return settings


async def main():

    # Загружаем настройки
    settings = load_settings()

    welcome_text = settings["welcome_text"]

    # Создаём бота и диспетчер
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    try:
        # Инициализация базы пользователей
        await init_db()

        # Обработчик команды START
        @dp.message(CommandStart())
        async def start_handler(message: Message):

            await register_user(bot, message.from_user)

            await message.answer(welcome_text)

        # Загрузка дополнительных модулей
        await load_modules(bot, dp)

        print("Бот успешно запущен!")

        # Запуск бота
        await dp.start_polling(bot)

    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
