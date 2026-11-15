from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery


order = 3

MENU_ITEMS = [
    {
        "text": "Регистрация",
        "callback_data": "menu:support"
    }
]


async def setup(bot: Bot, dp: Dispatcher):

    @dp.callback_query(F.data == "menu:support")
    async def support_handler(callback: CallbackQuery):

        await callback.message.answer(
            "Вакансии:/n- Купер/n📌 https://clck.ru/3Wiym2/n- Яндекс/n📌 https://clck.ru/3Wiymv/n/n"
        )

        await callback.answer()
