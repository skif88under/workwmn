import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)


order = 2

MENU_ITEMS = [
    {
        "text": "Частые вопросы",
        "callback_data": "faq:open"
    }
]


def load_faq():
    faq_path = Path(__file__).with_name("faq.json")

    with open(faq_path, "r", encoding="utf-8") as file:
        data = json.load(file)

    questions = data.get("questions")

    if not isinstance(questions, list) or not questions:
        raise ValueError("В faq.json должен быть непустой список questions")

    for item in questions:
        if not isinstance(item, dict) or not item.get("question") or not item.get("answer"):
            raise ValueError("Каждый вопрос FAQ должен содержать question и answer")

    return data


def build_questions_keyboard(questions):
    keyboard = [
        [
            InlineKeyboardButton(
                text=item["question"],
                callback_data=f"faq:q:{index}"
            )
        ]
        for index, item in enumerate(questions)
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def setup(bot: Bot, dp: Dispatcher):
    faq = load_faq()
    questions = faq["questions"]
    title = faq.get("title", "Выберите интересующий вопрос:")

    @dp.callback_query(F.data == "faq:open")
    async def faq_open_handler(callback: CallbackQuery):
        await callback.message.answer(
            title,
            reply_markup=build_questions_keyboard(questions)
        )
        await callback.answer()

    @dp.callback_query(F.data.startswith("faq:q:"))
    async def faq_question_handler(callback: CallbackQuery):
        try:
            index = int(callback.data.rsplit(":", 1)[1])
            item = questions[index]
        except (ValueError, IndexError):
            await callback.answer("Вопрос не найден.", show_alert=True)
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="← Назад к вопросам",
                        callback_data="faq:back"
                    )
                ]
            ]
        )

        await callback.message.edit_text(
            f"<b>{item['question']}</b>\n\n{item['answer']}",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        await callback.answer()

    @dp.callback_query(F.data == "faq:back")
    async def faq_back_handler(callback: CallbackQuery):
        await callback.message.edit_text(
            title,
            reply_markup=build_questions_keyboard(questions)
        )
        await callback.answer()
