
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

order = 4

# Укажи здесь username нужного Telegram-аккаунта
TELEGRAM_USERNAME = "kye707"

MENU_ITEMS = [
    {
        "text": "Написать менеджеру",
        "callback_data": "menu:link"
    }
]


async def setup(bot: Bot, dp: Dispatcher):
    @dp.callback_query(lambda callback: callback.data == "menu:link")
    async def link_handler(callback):
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Перейти в Telegram",
                        url=f"https://t.me/{TELEGRAM_USERNAME}"
                    )
                ]
            ]
        )

        await callback.message.answer(
            "Нажмите кнопку ниже, чтобы перейти в наш Telegram-аккаунт:",
            reply_markup=keyboard
        )

        await callback.answer()
