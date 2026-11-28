import asyncio
import logging

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.user_logger import DB_PATH


logger = logging.getLogger(__name__)

BROADCAST_INTERVAL_DAYS = 3
SEND_INTERVAL_SECONDS = 1.2
CHECK_INTERVAL_SECONDS = 30

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
                next_run_at TEXT NOT NULL,
                campaign_active INTEGER NOT NULL DEFAULT 0,
                sent_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS broadcast_queue (
                user_id INTEGER PRIMARY KEY
            )
        """)
        # Первая рассылка запускается через три дня после первого старта новой версии.
        await db.execute("""
            INSERT OR IGNORE INTO broadcast_state (
                id, next_run_at, campaign_active
            )
            VALUES (
                1,
                datetime('now', '+3 days'),
                0
            )
        """)
        await db.commit()


async def get_broadcast_recipient():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM broadcast_queue ORDER BY user_id LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def prepare_or_finish_campaign():
    """Создаёт очередь по расписанию или завершает полностью отправленную кампанию."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT next_run_at, campaign_active FROM broadcast_state WHERE id = 1"
        )
        state = await cursor.fetchone()

        if state is None:
            await db.execute("""
                INSERT INTO broadcast_state (id, next_run_at, campaign_active)
                VALUES (1, datetime('now', '+3 days'), 0)
            """)
            await db.commit()
            return False

        next_run_at, campaign_active = state

        if campaign_active:
            cursor = await db.execute("SELECT COUNT(*) FROM broadcast_queue")
            remaining = (await cursor.fetchone())[0]

            if remaining == 0:
                await db.execute("""
                    UPDATE broadcast_state
                    SET campaign_active = 0,
                        next_run_at = datetime('now', '+3 days')
                    WHERE id = 1
                """)
                await db.commit()
                logger.info("Рассылка завершена. Следующая запланирована через 3 дня.")
                return False

            return True

        cursor = await db.execute(
            "SELECT datetime('now') >= ?",
            (next_run_at,)
        )
        due = (await cursor.fetchone())[0]

        if not due:
            return False

        await db.execute("""
            INSERT OR IGNORE INTO broadcast_queue (user_id)
            SELECT user_id FROM users ORDER BY user_id
        """)
        cursor = await db.execute("SELECT COUNT(*) FROM broadcast_queue")
        total = (await cursor.fetchone())[0]

        await db.execute("""
            UPDATE broadcast_state
            SET campaign_active = 1, sent_count = 0, failed_count = 0
            WHERE id = 1
        """)
        await db.commit()

        logger.info("Начинается рассылка напоминания о бонусе. Получателей: %s", total)
        return True


async def mark_recipient_done(user_id: int, sent: bool):
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


async def run_broadcast_worker(bot: Bot):
    """Раз в три дня отправляет напоминание всем пользователям из SQLite."""
    await init_broadcast_db()
    logger.info("Планировщик рассылки бонуса запущен (интервал: 3 дня)")

    while True:
        try:
            active = await prepare_or_finish_campaign()

            if not active:
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue

            user_id = await get_broadcast_recipient()
            if user_id is None:
                await asyncio.sleep(2)
                continue

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=BONUS_TEXT,
                    reply_markup=BONUS_KEYBOARD
                )
                await mark_recipient_done(user_id, sent=True)
                logger.info("Напоминание о бонусе отправлено user_id=%s", user_id)
                await asyncio.sleep(SEND_INTERVAL_SECONDS)

            except TelegramRetryAfter as error:
                delay = error.retry_after + 2
                logger.warning(
                    "Telegram ограничил рассылку. Повтор через %s сек.; user_id=%s",
                    delay,
                    user_id
                )
                await asyncio.sleep(delay)

            except (TelegramForbiddenError, TelegramBadRequest) as error:
                logger.info(
                    "Пользователю %s нельзя доставить рассылку; пропускаю: %s",
                    user_id,
                    error
                )
                await mark_recipient_done(user_id, sent=False)
                await asyncio.sleep(SEND_INTERVAL_SECONDS)

        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Ошибка планировщика рассылки; повтор через 30 секунд")
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)
