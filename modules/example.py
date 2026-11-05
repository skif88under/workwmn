from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


order = 1


async def setup(bot: Bot, dp: Dispatcher):

    @dp.message(Command("hello"))
    async def hello_handler(message: Message):

        await message.answer(
            "Привет! Это дополнительный модуль."
        )
