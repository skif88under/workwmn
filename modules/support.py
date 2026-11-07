from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery


order = 3

MENU_ITEMS = [
    {
        "text": "Связь с менеджером",
        "callback_data": "menu:support"
    }
]


async def setup(bot: Bot, dp: Dispatcher):

    @dp.callback_query(F.data == "menu:support")
    async def support_handler(callback: CallbackQuery):

        await callback.message.answer(
            "У вас возникли вопросы связанные с регистрацией или желаете уточнить по поводу работы?/n/nПишите сюда - @kye707"
        )

        await callback.answer()
