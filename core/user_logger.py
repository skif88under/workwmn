import aiosqlite

from pathlib import Path
from aiogram.types import User


DB_PATH = Path(__file__).resolve().parent.parent / "users.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                welcome_message_id INTEGER
            )
        """)

        # Добавляем поле существующим базам данных без потери пользователей.
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "welcome_message_id" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN welcome_message_id INTEGER"
            )

        # Очередь уведомлений сохраняется в SQLite и переживает перезапуск бота.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS notification_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()


async def get_welcome_message_id(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT welcome_message_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

    return row[0] if row else None


async def save_welcome_message_id(user_id: int, message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET welcome_message_id = ? WHERE user_id = ?",
            (message_id, user_id)
        )
        await db.commit()


async def register_user(user: User):
    username = f"@{user.username}" if user.username else "Отсутствует"
    first_name = user.first_name or "Не указано"
    last_name = user.last_name or ""

    notification_text = (
        "🆕 Новый пользователь запустил бота\n\n"
        f"👤 Имя: {first_name} {last_name}\n"
        f"🔗 Username: {username}\n"
        f"🆔 ID: {user.id}"
    )

    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user.id,)
        )
        exists = await cursor.fetchone()

        if exists:
            return False

        # Регистрация и постановка уведомления в очередь — одна транзакция.
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

        await db.execute(
            "INSERT INTO notification_queue (message_text) VALUES (?)",
            (notification_text,)
        )

        await db.commit()

    return True


async def get_next_notification():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, message_text FROM notification_queue ORDER BY id LIMIT 1"
        )
        return await cursor.fetchone()


async def delete_notification(notification_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "DELETE FROM notification_queue WHERE id = ?",
            (notification_id,)
        )
        await db.commit()
