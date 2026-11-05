from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message


order = 3


async def setup(bot: Bot, dp: Dispatcher):

    @dp.message(Command("support"))
    async def support_handler(message: Message):

        await message.answer(
            "Связаться с поддержкой: @support"
        )
