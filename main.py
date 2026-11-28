import asyncio
import json
import logging

from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)

from config import BOT_TOKEN, LOG_CHAT_ID
from core.loader import load_modules
from modules.broadcast import run_broadcast_worker
from core.user_logger import (
    init_db,
    register_user,
    get_next_notification,
    delete_notification,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)
logger = logging.getLogger(__name__)


def load_settings():
    settings_path = Path(__file__).parent / "settings.json"

    with open(settings_path, "r", encoding="utf-8") as file:
        settings = json.load(file)

    return settings


def build_menu(menu_items):
    buttons = []

    for item in menu_items:
        if item.get("url"):
            button = InlineKeyboardButton(
                text=item["text"],
                url=item["url"]
            )
        else:
            button = InlineKeyboardButton(
                text=item["text"],
                callback_data=item["callback_data"]
            )

        buttons.append([button])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def notification_worker(bot: Bot):
    """Постепенно отправляет накопившиеся уведомления о новых пользователях."""
    logger.info("Запущен фоновый обработчик очереди уведомлений")

    while True:
        notification = await get_next_notification()

        if notification is None:
            await asyncio.sleep(1)
            continue

        notification_id, notification_text = notification

        try:
            await bot.send_message(LOG_CHAT_ID, notification_text)
            await delete_notification(notification_id)
            logger.info(
                "Уведомление из очереди отправлено (id=%s)",
                notification_id
            )

            # В группах Telegram действует лимит около 20 сообщений в минуту.
            # Интервал 3.2 секунды оставляет небольшой запас.
            await asyncio.sleep(3.2)

        except TelegramRetryAfter as error:
            delay = error.retry_after + 2
            logger.warning(
                "Telegram ограничил отправку в чат БД. "
                "Повтор через %s сек.; уведомление id=%s останется в очереди.",
                delay,
                notification_id
            )
            await asyncio.sleep(delay)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "Не удалось отправить уведомление id=%s. "
                "Оно останется в очереди.",
                notification_id
            )
            await asyncio.sleep(10)


async def main():
    settings = load_settings()

    welcome_text = settings.get(
        "welcome_text",
        "Привет! Добро пожаловать."
    )

    welcome_image = settings.get("welcome_image")

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    notification_task = None
    broadcast_task = None

    try:
        logger.info("Инициализация базы данных...")
        await init_db()

        logger.info("Загрузка модулей...")
        menu_items = await load_modules(bot, dp)
        menu = build_menu(menu_items) if menu_items else None

        # Уведомления отправляются независимо от обработки команд пользователей.
        notification_task = asyncio.create_task(notification_worker(bot))
        broadcast_task = asyncio.create_task(run_broadcast_worker(bot))

        @dp.message(CommandStart())
        async def start_handler(message: Message):
            user_id = message.from_user.id
            logger.info("Получена команда /start от user_id=%s", user_id)

            await register_user(message.from_user)

            # При каждом /start отправляем новое приветствие.
            # Регистрация и уведомление в чат БД остаются только для новых пользователей.
            if welcome_image:
                image_path = Path(__file__).parent / welcome_image

                if image_path.is_file():
                    photo = FSInputFile(image_path)
                    await message.answer_photo(
                        photo=photo,
                        caption=welcome_text,
                        reply_markup=menu
                    )
                else:
                    logger.error("Изображение приветствия не найдено: %s", image_path)
                    await message.answer(
                        welcome_text,
                        reply_markup=menu
                    )
            else:
                await message.answer(
                    welcome_text,
                    reply_markup=menu
                )

        # Не вызываем delete_webhook при каждом старте.
        logger.info("Модули загружены. Запускаю Telegram polling...")

        while True:
            try:
                await dp.start_polling(bot)
                break
            except TelegramRetryAfter as error:
                delay = error.retry_after + 2
                logger.warning(
                    "Telegram ограничил частоту запросов. Повтор через %s сек.",
                    delay
                )
                await asyncio.sleep(delay)

    except Exception:
        logger.exception("Критическая ошибка при работе бота")
        raise
    finally:
        if broadcast_task is not None:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass

        if notification_task is not None:
            notification_task.cancel()
            try:
                await notification_task
            except asyncio.CancelledError:
                pass

        await bot.session.close()
        logger.info("Сессия бота закрыта")


if __name__ == "__main__":
    asyncio.run(main())
