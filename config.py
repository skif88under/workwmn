import os


BOT_TOKEN = os.getenv("BOT_TOKEN")
LOG_CHAT_ID = os.getenv("LOG_CHAT_ID")


if not BOT_TOKEN:
    raise RuntimeError("Не задана переменная BOT_TOKEN")

if not LOG_CHAT_ID:
    raise RuntimeError("Не задана переменная LOG_CHAT_ID")

try:
    LOG_CHAT_ID = int(LOG_CHAT_ID)
except ValueError:
    raise RuntimeError("LOG_CHAT_ID должен быть числом")
