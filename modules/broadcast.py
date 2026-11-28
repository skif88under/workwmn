import asyncio
import logging

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from core.user_logger import DB_PATH


logger = logging.getLogger(__name__)

ADMIN_ID = 8611309490
SEND_INTERVAL_SECONDS = 1.2

BONUS_TEXT = (
    "🎁 Напоминаем о денежном бонусе!\n\n"
    "При регистрации можно получить дополнительный бонус. "
    "Размер и условия зависят от города, в котором собираетесь работать.\n\n"
    "Чтобы узнать подробности, напишите менеджеру."
)

BONUS_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Узнать о бонусе",
                url="https://t.me/kye707"
            )
        ]
    ]
)


async def init_broadcast_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                next_run_at TEXT,
                campaign_active INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                total_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        # Совместимость с таблицей, созданной предыдущей версией
        # автоматической рассылки.
        cursor = await db.execute("PRAGMA table_info(broadcast_state)")
        columns = {row[1] for row in await cursor.fetchall()}
        legacy_scheduler_schema = "total_count" not in columns
        if legacy_scheduler_schema:
            await db.execute(
                "ALTER TABLE broadcast_state ADD COLUMN total_count INTEGER NOT NULL DEFAULT 0"
            )

        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_queue (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # next_run_at оставлен для совместимости со старой схемой SQLite.
        await db.execute("""
            INSERT OR IGNORE INTO broadcast_state (
                id, next_run_at, campaign_active, sent_count, failed_count, total_count
            )
            VALUES (1, datetime('now'), 0, 0, 0, 0)
        """)
        # Не продолжаем автоматически созданную старой версией кампанию:
        # теперь рассылка запускается только вручную администратором.
        if legacy_scheduler_schema:
            await db.execute("DELETE FROM broadcast_queue")
            await db.execute(
                "UPDATE broadcast_state SET campaign_active = 0 WHERE id = 1"
            )

        await db.commit()


async def get_broadcast_status():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT campaign_active, sent_count, failed_count, total_count
            FROM broadcast_state
            WHERE id = 1
        """)
        return await cursor.fetchone()


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        return (await cursor.fetchone())[0]


async def start_campaign():
    """Создаёт устойчивую SQLite-очередь для подтверждённой рассылки."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT campaign_active FROM broadcast_state WHERE id = 1"
        )
        row = await cursor.fetchone()

        if row and row[0]:
            return None

        await db.execute("DELETE FROM broadcast_queue")
        await db.execute("""
            INSERT INTO broadcast_queue (user_id)
            SELECT user_id FROM users ORDER BY user_id
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM broadcast_queue")
        total = (await cursor.fetchone())[0]

        await db.execute("""
            UPDATE broadcast_state
            SET campaign_active = 1,
                sent_count = 0,
                failed_count = 0,
                total_count = ?
            WHERE id = 1
        """, (total,))
        await db.commit()

    return total


async def get_next_recipient():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM broadcast_queue ORDER BY user_id LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def finish_recipient(user_id: int, sent: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM broadcast_queue WHERE user_id = ?",
            (user_id,)
        )
        column = "sent_count" if sent else "failed_count"
        await db.execute(
            f"UPDATE broadcast_state SET {column} = {column} + 1 WHERE id = 1"
        )
        await db.commit()


async def finish_campaign():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE broadcast_state SET campaign_active = 0 WHERE id = 1"
        )
        cursor = await db.execute("""
            SELECT sent_count, failed_count, total_count
            FROM broadcast_state WHERE id = 1
        """)
        result = await cursor.fetchone()
        await db.commit()
        return result


async def broadcast_worker(bot: Bot):
    logger.info("Начата ручная рассылка бонуса")

    while True:
        user_id = await get_next_recipient()
        if user_id is None:
            break

        try:
            await bot.send_message(
                chat_id=user_id,
                text=BONUS_TEXT,
                reply_markup=BONUS_KEYBOARD
            )
            await finish_recipient(user_id, sent=True)
            await asyncio.sleep(SEND_INTERVAL_SECONDS)

        except TelegramRetryAfter as error:
            delay = error.retry_after + 2
            logger.warning(
                "Flood control рассылки: пауза %s сек.; user_id=%s",
                delay,
                user_id
            )
            await asyncio.sleep(delay)

        except (TelegramForbiddenError, TelegramBadRequest) as error:
            logger.info(
                "Не удалось доставить рассылку user_id=%s; пропускаю: %s",
                user_id,
                error
            )
            await finish_recipient(user_id, sent=False)
            await asyncio.sleep(SEND_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            raise

        except Exception:
            # При временной сетевой ошибке адресат остаётся в очереди.
            logger.exception(
                "Временная ошибка отправки user_id=%s; повтор через 10 секунд",
                user_id
            )
            await asyncio.sleep(10)

    sent, failed, total = await finish_campaign()
    try:
        await bot.send_message(
            ADMIN_ID,
            "✅ Рассылка завершена.\n\n"
            f"Всего получателей: {total}\n"
            f"Успешно отправлено: {sent}\n"
            f"Не доставлено: {failed}"
        )
    except Exception:
        logger.exception("Не удалось отправить администратору итог рассылки")


async def setup(bot: Bot, dp: Dispatcher):
    await init_broadcast_db()
    worker_task = None

    async def start_worker():
        nonlocal worker_task
        if worker_task is None or worker_task.done():
            worker_task = asyncio.create_task(broadcast_worker(bot))

    # Если процесс перезапустился посреди рассылки, продолжаем сохранённую очередь.
    status = await get_broadcast_status()
    if status and status[0]:
        await start_worker()

    @dp.message(Command("broadcast"))
    async def broadcast_command(message: Message):
        if message.from_user.id != ADMIN_ID:
            return

        if message.chat.type != "private":
            await message.answer("Команду рассылки можно запускать только в личном чате с ботом.")
            return

        status = await get_broadcast_status()
        if status and status[0]:
            await message.answer(
                "Рассылка уже выполняется. Дождись итогового отчёта."
            )
            return

        total = await get_user_count()
        if total == 0:
            await message.answer("В базе пока нет пользователей для рассылки.")
            return

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="✅ Подтвердить рассылку",
                        callback_data="broadcast:confirm"
                    ),
                    InlineKeyboardButton(
                        text="Отмена",
                        callback_data="broadcast:cancel"
                    )
                ]
            ]
        )
        await message.answer(
            f"Подготовить напоминание о бонусе для {total} пользователей?\n\n"
            "Сообщения будут отправляться постепенно. Пользователи, "
            "которые заблокировали бота, будут пропущены.",
            reply_markup=keyboard
        )

    @dp.callback_query(F.data == "broadcast:confirm")
    async def broadcast_confirm(callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("Нет доступа.", show_alert=True)
            return

        total = await start_campaign()
        if total is None:
            await callback.answer("Рассылка уже запущена.", show_alert=True)
            return

        await callback.message.edit_text(
            f"Рассылка запущена. Получателей в очереди: {total}.\n"
            "По завершении я пришлю статистику."
        )
        await callback.answer()
        await start_worker()

    @dp.callback_query(F.data == "broadcast:cancel")
    async def broadcast_cancel(callback: CallbackQuery):
        if callback.from_user.id != ADMIN_ID:
            await callback.answer("Нет доступа.", show_alert=True)
            return

        await callback.message.edit_text("Рассылка отменена.")
        await callback.answer()
