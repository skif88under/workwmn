import aiosqlite

from pathlib import Path
from aiogram import Bot
from aiogram.types import User

from config import LOG_CHAT_ID


DB_PATH = Path(__file__).resolve().parent.parent / "users.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


async def register_user(bot: Bot, user: User):
    async with aiosqlite.connect(DB_PATH) as db:

        cursor = await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user.id,)
        )

        exists = await cursor.fetchone()

        if exists:
            return False

        await db.execute("""
            INSERT INTO users (
                user_id,
                username,
                first_name,
                last_name
            )
            VALUES (?, ?, ?, ?)
        """, (
            user.id,
            user.username,
            user.first_name,
            user.last_name
        ))

        await db.commit()

    username = f"@{user.username}" if user.username else "Отсутствует"
    first_name = user.first_name or "Не указано"
    last_name = user.last_name or ""

    text = (
        "🆕 Новый пользователь запустил бота\n\n"
        f"👤 Имя: {first_name} {last_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: {user.id}"
    )

    try:
        await bot.send_message(LOG_CHAT_ID, text)

    except Exception as error:
        print(f"Ошибка отправки уведомления: {error}")

    return True
