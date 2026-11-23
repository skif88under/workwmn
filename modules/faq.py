import json
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.types import CallbackQuery


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


async def setup(bot: Bot, dp: Dispatcher):
    faq = load_faq()
    questions = faq["questions"]
    title = faq.get("title", "Частые вопросы:")

    faq_text = title + "\n\n" + "\n\n".join(
        f"{index}. {item['question']}\n{item['answer']}"
        for index, item in enumerate(questions, start=1)
    )

    @dp.callback_query(F.data == "faq:open")
    async def faq_open_handler(callback: CallbackQuery):
        await callback.message.answer(faq_text)
        await callback.answer()
