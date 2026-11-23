from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery


order = 3

MENU_ITEMS = [
    {
        "text": "Денежный бонус при регистрации",
        "callback_data": "menu:bonus"
    }
]


async def setup(bot: Bot, dp: Dispatcher):

    @dp.callback_query(F.data == "menu:bonus")
    async def bonus_handler(callback: CallbackQuery):
        await callback.message.answer(
            "Вы можете получить денежный бонус при выполнении условий. "
            "Размер и условия зависят от города, в котором собираетесь работать"
        )
        await callback.answer()
