from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery


order = 3

MENU_ITEMS = [
    {
        "text": "🆘 Поддержка",
        "callback_data": "menu:support"
    }
]


async def setup(bot: Bot, dp: Dispatcher):

    @dp.callback_query(F.data == "menu:support")
    async def support_handler(callback: CallbackQuery):

        await callback.message.answer(
            "Связаться с поддержкой: @support"
        )

        await callback.answer()
